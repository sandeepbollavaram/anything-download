"""Browser (Chromium) network containment.

Two layers protect browser rendering: every sub-request is re-checked against
the SSRF policy, and the navigation host is pinned inside Chromium's own
resolver so the policy's lookup and the browser's lookup cannot disagree.
"""

from __future__ import annotations

import pytest

from anything_download.config import Settings
from anything_download.media.browser import _HostPolicy, host_resolver_rules
from anything_download.security.urls import ValidatedURL, validate_and_resolve


@pytest.mark.security
async def test_navigation_host_is_pinned_to_validated_ip(public_dns, settings: Settings) -> None:
    public_dns("pinned.example", "93.184.216.34")
    url = await validate_and_resolve("https://pinned.example/page", settings)

    rules = host_resolver_rules(url, settings)

    assert rules == "MAP pinned.example 93.184.216.34"


@pytest.mark.security
async def test_pinning_preserves_hostname_for_tls(public_dns, settings: Settings) -> None:
    """The hostname must survive: rewriting the URL to an IP would break SNI/cert checks."""
    public_dns("tls.example", "93.184.216.34")
    url = await validate_and_resolve("https://tls.example/page", settings)

    rules = host_resolver_rules(url, settings)

    assert rules is not None
    assert "tls.example" in rules
    assert url.host == "tls.example"


@pytest.mark.security
def test_no_pinning_for_ip_literal_targets(settings: Settings) -> None:
    url = ValidatedURL(
        url="https://93.184.216.34/x",
        scheme="https",
        host="93.184.216.34",
        port=443,
        path="/x",
        query="",
        is_ip_literal=True,
        resolved_ips=("93.184.216.34",),
    )

    assert host_resolver_rules(url, settings) is None


@pytest.mark.security
def test_ipv6_pin_is_bracketed(settings: Settings) -> None:
    url = ValidatedURL(
        url="https://v6.example/x",
        scheme="https",
        host="v6.example",
        port=443,
        path="/x",
        query="",
        is_ip_literal=False,
        resolved_ips=("2606:2800:220:1:248:1893:25c8:1946",),
    )

    rules = host_resolver_rules(url, settings)

    assert rules == "MAP v6.example [2606:2800:220:1:248:1893:25c8:1946]"


@pytest.mark.security
@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://[::1]/",
        "http://localhost/",
    ],
)
async def test_policy_blocks_private_subresources(target: str, settings: Settings) -> None:
    policy = _HostPolicy(settings)

    assert await policy.allowed(target) is False


@pytest.mark.security
async def test_policy_blocks_host_that_rebinds_to_private(public_dns, settings: Settings) -> None:
    """A hostname resolving to a private address is refused even though it looks public."""
    public_dns("rebind.example", "127.0.0.1")
    policy = _HostPolicy(settings)

    assert await policy.allowed("https://rebind.example/x") is False


@pytest.mark.security
async def test_policy_allows_public_host(public_dns, settings: Settings) -> None:
    public_dns("ok.example", "93.184.216.34")
    policy = _HostPolicy(settings)

    assert await policy.allowed("https://ok.example/x") is True


@pytest.mark.security
async def test_policy_rejects_non_http_schemes(settings: Settings) -> None:
    policy = _HostPolicy(settings)

    assert await policy.allowed("file:///etc/passwd") is False
    assert await policy.allowed("ftp://example.com/x") is False
