"""Rate-limit identity behind a reverse proxy.

The limiter keys on ``client_ip``. If a client-supplied ``X-Forwarded-For`` value
is trusted, rotating it defeats per-IP limits, so only the hop appended by the
trusted proxy may be used.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from anything_download.api.state import client_ip
from anything_download.config import Settings


def _request(headers: dict[str, str], peer: str = "10.0.0.5") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 1234),
        }
    )


@pytest.mark.security
def test_forged_leading_forwarded_for_entries_are_ignored(settings: Settings) -> None:
    trusted = settings.model_copy(update={"trust_proxy_headers": True})
    # nginx `$proxy_add_x_forwarded_for` appends the real peer after the client's value.
    forged = _request({"X-Forwarded-For": "203.0.113.9, 198.51.100.7"})
    assert client_ip(forged, trusted) == "198.51.100.7"


@pytest.mark.security
def test_rotating_a_forged_header_does_not_change_identity(settings: Settings) -> None:
    trusted = settings.model_copy(update={"trust_proxy_headers": True})
    identities = {
        client_ip(_request({"X-Forwarded-For": f"203.0.113.{i}, 198.51.100.7"}), trusted)
        for i in range(20)
    }
    assert identities == {"198.51.100.7"}


@pytest.mark.security
def test_single_proxy_set_value_is_used(settings: Settings) -> None:
    trusted = settings.model_copy(update={"trust_proxy_headers": True})
    assert client_ip(_request({"X-Forwarded-For": "198.51.100.7"}), trusted) == "198.51.100.7"
    assert client_ip(_request({"X-Forwarded-For": " , 198.51.100.7 ,"}), trusted) == "198.51.100.7"


@pytest.mark.security
def test_headers_ignored_unless_proxy_is_trusted(settings: Settings) -> None:
    untrusted = settings.model_copy(update={"trust_proxy_headers": False})
    request = _request({"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.10"})
    assert client_ip(request, untrusted) == "10.0.0.5"
