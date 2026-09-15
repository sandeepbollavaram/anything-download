import ipaddress

import pytest

from anything_download.errors import AppError, ErrorCode
from anything_download.security.urls import (
    interpret_ip,
    is_blocked_hostname,
    is_blocked_ip,
    normalize_url,
    parse_url,
    resolve_host,
    validate_and_resolve,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com/"),
        ("  HTTPS://Example.COM/Path?q=1#frag ", "https://example.com/Path?q=1"),
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("https://example.com:8443/a", "https://example.com:8443/a"),
        ("//cdn.example.com/x.png", "https://cdn.example.com/x.png"),
        ("https://example.com/a b", "https://example.com/a%20b"),
        ("https://bücher.example/x", "https://xn--bcher-kva.example/x"),
        ("https://example.com.", "https://example.com/"),
        ("<https://example.com/y>", "https://example.com/y"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", ErrorCode.INVALID_URL),
        ("   ", ErrorCode.INVALID_URL),
        ("javascript:alert(1)", ErrorCode.UNSUPPORTED_SCHEME),
        ("data:text/html,hi", ErrorCode.UNSUPPORTED_SCHEME),
        ("file:///etc/passwd", ErrorCode.UNSUPPORTED_SCHEME),
        ("ftp://example.com/x", ErrorCode.UNSUPPORTED_SCHEME),
        ("gopher://example.com", ErrorCode.UNSUPPORTED_SCHEME),
        ("mailto:a@b.c", ErrorCode.UNSUPPORTED_SCHEME),
        ("https://user:pass@example.com/", ErrorCode.INVALID_URL),
        ("https://example.com/\x00", ErrorCode.INVALID_URL),
        ("https://exa mple.com/", ErrorCode.INVALID_URL),
        ("https://", ErrorCode.INVALID_URL),
        ("https:///path", ErrorCode.INVALID_URL),
        ("https://example.com:99999/", ErrorCode.INVALID_URL),
        ("https://-bad-.example.com/", ErrorCode.INVALID_URL),
        ("https://a" + "b" * 3000 + ".com", ErrorCode.URL_TOO_LONG),
    ],
)
def test_reject(raw: str, code: ErrorCode) -> None:
    with pytest.raises(AppError) as exc:
        normalize_url(raw)
    assert exc.value.code == code


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "127.1.2.3",
        "0.0.0.0",
        "10.0.0.5",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "192.0.0.192",
        "198.18.0.1",
        "224.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fd12:3456::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "64:ff9b::7f00:1",
        "2002:7f00:0001::",
        "2001:db8::1",
    ],
)
def test_blocked_ips(ip: str) -> None:
    assert is_blocked_ip(ip)


@pytest.mark.parametrize(
    "ip",
    ["93.184.216.34", "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "2a00:1450:4001:80b::200e"],
)
def test_public_ips(ip: str) -> None:
    assert not is_blocked_ip(ip)


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST",
        "foo.localhost",
        "router.local",
        "svc.internal",
        "metadata.google.internal",
        "kubernetes.default.svc",
        "x.home.arpa",
        "something.onion",
    ],
)
def test_blocked_hostnames(host: str) -> None:
    assert is_blocked_hostname(host)


@pytest.mark.parametrize(
    "raw",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/admin",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/",
        "http://192.168.0.1/",
        "http://[fe80::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://intranet/",
        "http://db.internal/",
        "http://2130706433/",
        "http://127.1/",
        "http://0x7f.0.0.1/",
        "http://0177.0.0.1/",
        "http://0x7f000001/",
    ],
)
def test_parse_rejects_private_targets(raw: str) -> None:
    with pytest.raises(AppError) as exc:
        parse_url(raw)
    assert exc.value.code == ErrorCode.BLOCKED_TARGET


def test_parse_ok() -> None:
    p = parse_url("Example.com/file.PDF?x=1")
    assert p.host == "example.com"
    assert p.port == 443
    assert p.scheme == "https"
    assert p.filename_hint == "file.PDF"
    assert p.origin == "https://example.com"


async def test_resolve_blocks_private_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    from anything_download.security import urls as mod

    async def fake(host: str, port: int, *, timeout: float = 5.0) -> tuple[str, ...]:
        return ("93.184.216.34", "10.0.0.7")  # split answer: one public, one private

    monkeypatch.setattr(mod, "resolve_host", fake)
    with pytest.raises(AppError) as exc:
        await validate_and_resolve("https://evil.example/")
    assert exc.value.code == ErrorCode.BLOCKED_TARGET


async def test_resolve_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from anything_download.security import urls as mod

    async def fake(host: str, port: int, *, timeout: float = 5.0) -> tuple[str, ...]:
        return ("93.184.216.34",)

    monkeypatch.setattr(mod, "resolve_host", fake)
    v = await validate_and_resolve("https://example.com/a")
    assert v.primary_ip == "93.184.216.34"
    assert v.url == "https://example.com/a"


async def test_resolve_failure_maps_to_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    from anything_download.security import urls as mod

    class Loop:
        async def getaddrinfo(self, *a, **k):  # type: ignore[no-untyped-def]
            raise socket.gaierror("nope")

    def running_loop() -> Loop:
        return Loop()

    monkeypatch.setattr(mod.asyncio, "get_running_loop", running_loop)
    with pytest.raises(AppError) as exc:
        await validate_and_resolve("https://does-not-exist.example/")
    assert exc.value.code == ErrorCode.SOURCE_UNREACHABLE


def test_allow_private_targets_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from anything_download import config

    monkeypatch.setenv("AD_ALLOW_PRIVATE_TARGETS", "true")
    config.reset_settings_cache()
    p = parse_url("http://127.0.0.1:9/")
    assert p.host == "127.0.0.1"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2130706433", "127.0.0.1"),
        ("127.1", "127.0.0.1"),
        ("0x7f.0.0.1", "127.0.0.1"),
        ("0177.0.0.1", "127.0.0.1"),
        ("0x7f000001", "127.0.0.1"),
        ("134744072", "8.8.8.8"),
    ],
)
def test_interpret_unusual_ipv4(raw: str, expected: str) -> None:
    assert interpret_ip(raw) == ipaddress.IPv4Address(expected)


def test_unusual_public_ipv4_is_allowed() -> None:
    assert not is_blocked_ip("134744072")
    parsed = parse_url("http://134744072/")
    assert parsed.is_ip_literal


@pytest.mark.asyncio
async def test_resolve_host_canonicalizes_weird_ipv4() -> None:
    assert await resolve_host("2130706433", 80) == ("127.0.0.1",)
    assert await resolve_host("134744072", 80) == ("8.8.8.8",)
