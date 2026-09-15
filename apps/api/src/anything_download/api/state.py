"""Application state and dependency providers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import redis.asyncio as aioredis
from fastapi import Request

from anything_download.config import Settings
from anything_download.jobs.store import JobStore
from anything_download.net.client import SafeHttpClient
from anything_download.storage.guard import StorageGuard
from anything_download.storage.local import LocalStorage


@dataclass
class AppState:
    settings: Settings
    redis: aioredis.Redis
    store: JobStore
    storage: LocalStorage
    http: SafeHttpClient

    @cached_property
    def guard(self) -> StorageGuard:
        return StorageGuard(self.settings, self.storage.root)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.ad
    return state


def get_settings_dep(request: Request) -> Settings:
    return get_state(request).settings


def get_store(request: Request) -> JobStore:
    return get_state(request).store


def get_storage(request: Request) -> LocalStorage:
    return get_state(request).storage


def get_http(request: Request) -> SafeHttpClient:
    return get_state(request).http


def client_ip(request: Request, settings: Settings) -> str:
    """Client address used for rate limiting.

    Behind a trusted proxy the *rightmost* ``X-Forwarded-For`` entry is used: it
    is the one the proxy appended, whereas everything to its left came from the
    client and can be forged. Taking the leftmost entry let a client rotate a fake
    header and escape per-IP rate limits entirely (verified against nginx with the
    usual ``$proxy_add_x_forwarded_for``). Behind more than one proxy hop the
    rightmost entry is the inner proxy, which errs toward over-throttling.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
            if hops:
                return hops[-1][:64]
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()[:64]
    return request.client.host if request.client else "unknown"
