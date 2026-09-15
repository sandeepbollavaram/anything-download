"""URL normalization, validation and SSRF protection.

Pipeline::

    raw string -> normalize_url -> parse_url (syntactic checks)
               -> resolve_and_check (DNS resolution + IP policy)

The resolved IP addresses are returned so the HTTP layer can connect to the
*validated* address instead of re-resolving the hostname (defeats DNS
rebinding). See :mod:`anything_download.net.client`.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit, urlunsplit

from anything_download.config import Settings, get_settings
from anything_download.errors import AppError, ErrorCode

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}

# Hostnames that must never be contacted regardless of DNS answers.
_BLOCKED_HOST_SUFFIXES = (
    "localhost",
    ".localhost",
    ".local",
    ".internal",
    ".localdomain",
    ".home.arpa",
    ".in-addr.arpa",
    ".ip6.arpa",
    ".onion",
)
_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata",
        "instance-data",
        "kubernetes.default",
        "kubernetes.default.svc",
        "169.254.169.254",
        "fd00:ec2::254",
        "100.100.100.200",  # Alibaba Cloud metadata
        "192.0.0.192",  # Oracle Cloud metadata
    }
)

_EXTRA_BLOCKED_V4 = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # shared address space (CGNAT)
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
)
_EXTRA_BLOCKED_V6 = (
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped (checked via inner v4 too)
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("100::/64"),
    ipaddress.ip_network("2001::/32"),  # Teredo
    ipaddress.ip_network("2001:db8::/32"),
    ipaddress.ip_network("2002::/16"),  # 6to4
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
)

_HOST_LABEL_RE = re.compile(r"^(?!-)[a-z0-9_-]{1,63}(?<!-)$")
# Decimal / octal / hex / shortened IPv4 (e.g. 2130706433, 127.1, 0x7f.0.0.1).
_WEIRD_V4 = re.compile(
    r"^(?:\d+|0x[0-9a-fA-F]+)(?:\.(?:\d+|0x[0-9a-fA-F]+)){0,3}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedURL:
    url: str
    scheme: str
    host: str
    """IDNA-encoded (ASCII) hostname, lowercase, or an IP literal."""
    port: int
    path: str
    query: str
    is_ip_literal: bool

    @property
    def origin(self) -> str:
        default = DEFAULT_PORTS[self.scheme]
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}" + ("" if self.port == default else f":{self.port}")

    @property
    def filename_hint(self) -> str:
        """Last path segment (percent-decoded), used as a naming hint only."""
        from urllib.parse import unquote

        segment = self.path.rsplit("/", 1)[-1]
        return unquote(segment)


@dataclass(frozen=True)
class ValidatedURL(ParsedURL):
    resolved_ips: tuple[str, ...] = field(default=())

    @property
    def primary_ip(self) -> str:
        return self.resolved_ips[0]


def is_blocked_ip(value: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the address is loopback/private/link-local/reserved/etc."""
    if isinstance(value, str):
        parsed = interpret_ip(value)
        if parsed is None:
            return True
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address = parsed
    else:
        ip = value
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None and is_blocked_ip(ip.ipv4_mapped):
            return True
        if ip.sixtofour is not None and is_blocked_ip(ip.sixtofour):
            return True
        if ip.teredo is not None and is_blocked_ip(ip.teredo[1]):
            return True
        # NAT64 embeds the IPv4 address in the low 32 bits.
        if ip in ipaddress.ip_network("64:ff9b::/96") and is_blocked_ip(
            ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        ):
            return True
        nets: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = _EXTRA_BLOCKED_V6
    else:
        nets = _EXTRA_BLOCKED_V4
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    return any(ip in net for net in nets)


def is_blocked_hostname(host: str) -> bool:
    h = host.lower().rstrip(".")
    if h in _BLOCKED_HOSTS or "." not in h:
        # Single-label names (intranet, router, printer) only resolve inside private networks.
        return True
    return any(h == s.lstrip(".") or h.endswith(s) for s in _BLOCKED_HOST_SUFFIXES)


def _idna_encode(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise AppError(ErrorCode.INVALID_URL, "The URL host name is not valid.") from exc


def normalize_url(raw: str, settings: Settings | None = None) -> str:
    """Normalize a user supplied URL string.

    * trims whitespace and surrounding angle brackets / quotes
    * prepends ``https://`` when the scheme is missing
    * lowercases scheme and host, applies IDNA encoding
    * removes default ports and fragments
    * ensures a non-empty path
    """
    settings = settings or get_settings()
    if not isinstance(raw, str):
        raise AppError(ErrorCode.INVALID_URL, "A URL string is required.")
    candidate = raw.strip().strip("<>\"'")
    if not candidate:
        raise AppError(ErrorCode.INVALID_URL, "Please paste a URL.")
    if len(candidate) > settings.max_url_length:
        raise AppError(
            ErrorCode.URL_TOO_LONG,
            f"URLs longer than {settings.max_url_length} characters are not supported.",
        )
    if any(ord(ch) < 0x20 or ch == "\x7f" for ch in candidate) or re.search(
        r"[\t\r\n\f\v]", candidate
    ):
        raise AppError(ErrorCode.INVALID_URL, "The URL contains invalid control characters.")
    # Users often paste paths containing literal spaces; encode rather than reject them.
    candidate = candidate.replace(" ", "%20")

    if "://" not in candidate:
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        elif re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", candidate) and not re.match(
            r"^[a-zA-Z0-9.-]+:\d+(/|$)", candidate
        ):
            # Looks like a non-http scheme such as javascript: / data: / mailto:
            scheme = candidate.split(":", 1)[0].lower()
            raise AppError(
                ErrorCode.UNSUPPORTED_SCHEME,
                f"The '{scheme}:' scheme is not supported. Only http and https URLs can be processed.",
            )
        else:
            candidate = "https://" + candidate

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise AppError(ErrorCode.INVALID_URL, "The URL could not be parsed.") from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise AppError(
            ErrorCode.UNSUPPORTED_SCHEME,
            f"The '{scheme}:' scheme is not supported. Only http and https URLs can be processed.",
        )
    if parts.username is not None or parts.password is not None:
        raise AppError(ErrorCode.INVALID_URL, "URLs containing credentials are not supported.")
    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise AppError(ErrorCode.INVALID_URL, "The URL port is not valid.") from exc
    if not hostname:
        raise AppError(ErrorCode.INVALID_URL, "The URL has no host name.")

    host = _idna_encode(hostname.rstrip("."))
    is_ip = _is_ip_literal(host)
    if not is_ip and not _valid_hostname(host):
        raise AppError(ErrorCode.INVALID_URL, "The URL host name is not valid.")
    netloc_host = f"[{host}]" if ":" in host else host
    if port is not None and port != DEFAULT_PORTS[scheme]:
        netloc = f"{netloc_host}:{port}"
    else:
        netloc = netloc_host

    path = parts.path or "/"
    # Re-quote the path conservatively so stray spaces / unicode become percent-encoded.
    path = quote(path, safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="=&%:@!$'()*+,;/?-._~")
    return urlunsplit((scheme, netloc, path, query, ""))


def _parse_ipv4_component(part: str) -> int | None:
    """Parse one IPv4 component as decimal, octal, or hex. Returns None if invalid."""
    if not part:
        return None
    try:
        lowered = part.lower()
        if lowered.startswith("0x"):
            if len(lowered) == 2:
                return None
            return int(lowered, 16)
        if len(part) > 1 and part[0] == "0" and all(ch in "01234567" for ch in part):
            return int(part, 8)
        if part.isdigit():
            return int(part, 10)
    except ValueError:
        return None
    return None


def _parse_weird_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """Parse decimal / hex / octal / shortened IPv4 without depending on inet_aton.

    Windows ``inet_aton`` rejects many of these forms; attackers still send them.
    Packing matches historic inet_aton: 1 part is 32-bit, 2 parts are a + 24-bit,
    3 parts are a.b + 16-bit, 4 parts are dotted octets.
    """
    if not _WEIRD_V4.match(host):
        return None
    parts = host.split(".")
    nums: list[int] = []
    for part in parts:
        value = _parse_ipv4_component(part)
        if value is None:
            return None
        nums.append(value)
    try:
        if len(nums) == 1:
            packed = nums[0]
            if packed > 0xFFFFFFFF:
                return None
        elif len(nums) == 2:
            if nums[0] > 0xFF or nums[1] > 0xFFFFFF:
                return None
            packed = (nums[0] << 24) | nums[1]
        elif len(nums) == 3:
            if nums[0] > 0xFF or nums[1] > 0xFF or nums[2] > 0xFFFF:
                return None
            packed = (nums[0] << 24) | (nums[1] << 16) | nums[2]
        elif len(nums) == 4:
            if any(n > 0xFF for n in nums):
                return None
            packed = (nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]
        else:
            return None
        return ipaddress.IPv4Address(packed)
    except (OverflowError, ValueError):
        return None


def interpret_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse a host as an IP, including unusual IPv4 spellings used to bypass filters."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return _parse_weird_ipv4(host)


def _is_ip_literal(host: str) -> bool:
    return interpret_ip(host) is not None


def _valid_hostname(host: str) -> bool:
    if len(host) > 253 or not host:
        return False
    labels = host.split(".")
    return all(_HOST_LABEL_RE.match(label) for label in labels)


def parse_url(raw: str, settings: Settings | None = None) -> ParsedURL:
    """Normalize and syntactically validate a URL, applying hostname policy."""
    settings = settings or get_settings()
    normalized = normalize_url(raw, settings)
    parts = urlsplit(normalized)
    host = parts.hostname or ""
    port = parts.port or DEFAULT_PORTS[parts.scheme]
    is_ip = _is_ip_literal(host)

    if not settings.allow_private_targets:
        parsed_ip = interpret_ip(host)
        if parsed_ip is not None and is_blocked_ip(parsed_ip):
            raise AppError(
                ErrorCode.BLOCKED_TARGET,
                "URLs pointing to private, local or reserved network addresses cannot be processed.",
            )
        if not is_ip and is_blocked_hostname(host):
            raise AppError(
                ErrorCode.BLOCKED_TARGET,
                "URLs pointing to local or internal host names cannot be processed.",
            )
    return ParsedURL(
        url=normalized,
        scheme=parts.scheme,
        host=host,
        port=port,
        path=parts.path,
        query=parts.query,
        is_ip_literal=is_ip,
    )


async def resolve_host(host: str, port: int, *, timeout: float = 5.0) -> tuple[str, ...]:
    """Resolve a hostname to all of its addresses (IPv4 first)."""
    parsed_ip = interpret_ip(host)
    if parsed_ip is not None:
        return (str(parsed_ip),)
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise AppError(ErrorCode.SOURCE_TIMEOUT, "Resolving the host name timed out.") from exc
    except (socket.gaierror, OSError) as exc:
        raise AppError(
            ErrorCode.SOURCE_UNREACHABLE, "The host name could not be resolved."
        ) from exc
    addresses: list[str] = []
    for family, _type, _proto, _canon, sockaddr in infos:
        addr = str(sockaddr[0])
        if family == socket.AF_INET6 and "%" in addr:  # strip scope id
            addr = addr.split("%", 1)[0]
        if addr not in addresses:
            addresses.append(addr)
    # Prefer IPv4 for connection stability, keep order otherwise.
    addresses.sort(key=lambda a: 0 if ":" not in a else 1)
    if not addresses:
        raise AppError(
            ErrorCode.SOURCE_UNREACHABLE, "The host name did not resolve to any address."
        )
    return tuple(addresses)


async def validate_and_resolve(raw: str, settings: Settings | None = None) -> ValidatedURL:
    """Full validation: syntax + hostname policy + DNS resolution + IP policy.

    Every resolved address must pass the IP policy; if a single answer points
    at a blocked range the URL is rejected (prevents split-horizon tricks).
    """
    settings = settings or get_settings()
    parsed = parse_url(raw, settings)
    ips = await resolve_host(parsed.host, parsed.port)
    if not settings.allow_private_targets and any(is_blocked_ip(ip) for ip in ips):
        raise AppError(
            ErrorCode.BLOCKED_TARGET,
            "The URL resolves to a private, local or reserved network address and cannot be processed.",
        )
    return ValidatedURL(
        url=parsed.url,
        scheme=parsed.scheme,
        host=parsed.host,
        port=parsed.port,
        path=parsed.path,
        query=parsed.query,
        is_ip_literal=parsed.is_ip_literal,
        resolved_ips=ips,
    )
