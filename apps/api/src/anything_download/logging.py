"""Structured logging with redaction of sensitive values.

We never log Authorization headers, cookies, credentials or query strings
(which may contain signed tokens). URLs are reduced to ``scheme://host/path``.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import structlog

_SENSITIVE_KEYS = re.compile(
    r"(authorization|cookie|set-cookie|token|secret|password|passwd|api[-_]?key|credential|signature)",
    re.IGNORECASE,
)
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def redact_url(url: str) -> str:
    """Strip query string, fragment and userinfo from a URL for logging."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid-url>"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _redact_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        if _SENSITIVE_KEYS.search(key):
            event_dict[key] = "[REDACTED]"
        elif key in {"url", "source_url", "target"} and isinstance(event_dict[key], str):
            event_dict[key] = redact_url(event_dict[key])
        elif key == "message" and isinstance(event_dict[key], str):
            event_dict[key] = _redact_urls_in_text(event_dict[key])
    return event_dict


def _redact_urls_in_text(text: str) -> str:
    return _URL_IN_TEXT.sub(lambda match: redact_url(match.group(0)), text)


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        numeric = logging.INFO

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_processor,
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Any
    if fmt == "json":
        shared.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)
    for noisy in ("uvicorn.access", "httpx", "httpcore", "yt_dlp"):
        logging.getLogger(noisy).setLevel(max(numeric, logging.WARNING))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
