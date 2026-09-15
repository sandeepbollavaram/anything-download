"""Global storage-pressure guard.

Per-request limits (upload size, output size, TTLs) bound a single request, not the
sum of all of them: many clients uploading at once can still fill the disk inside
one retention window. This guard is the global backstop. It refuses *new*
storage-consuming work (uploads and jobs) while the storage filesystem is below
a free-space floor or the storage directory is over its quota, and it aborts an
in-flight upload stream that crosses the floor. Work that was already admitted is
left to finish; the floor is sized so that it can.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from anything_download.config import Settings
from anything_download.errors import AppError, ErrorCode
from anything_download.logging import get_logger

log = get_logger(__name__)

_USAGE_TTL_SECONDS = 15.0
RETRY_AFTER_SECONDS = 120


@dataclass(frozen=True)
class StorageStatus:
    free_bytes: int
    used_bytes: int | None
    """Size of the storage directory; only measured when a quota is configured."""
    ok: bool


class StorageGuard:
    def __init__(self, settings: Settings, root: Path) -> None:
        self.settings = settings
        self.root = root
        self._lock = threading.Lock()
        self._usage: tuple[float, int] | None = None

    # -- measurement -------------------------------------------------------
    def free_bytes(self) -> int:
        try:
            return shutil.disk_usage(self.root).free
        except OSError:
            return 0  # an unreadable filesystem is treated as full: fail closed

    def used_bytes(self) -> int:
        """Total size of the storage directory, re-measured at most every 15 s."""
        now = time.monotonic()
        with self._lock:
            if self._usage is not None and now - self._usage[0] < _USAGE_TTL_SECONDS:
                return self._usage[1]
        total = _tree_size(self.root)
        with self._lock:
            self._usage = (now, total)
        return total

    def status(self) -> StorageStatus:
        free = self.free_bytes()
        used = self.used_bytes() if self.settings.max_storage_bytes else None
        return StorageStatus(free_bytes=free, used_bytes=used, ok=self._fits(free, used, 0))

    # -- enforcement ---------------------------------------------------------
    def _fits(self, free: int, used: int | None, incoming: int) -> bool:
        if free - incoming < self.settings.min_free_disk_bytes:
            return False
        quota = self.settings.max_storage_bytes
        return not (quota and used is not None and used + incoming > quota)

    def require(self, incoming_bytes: int = 0) -> None:
        """Raise ``STORAGE_FULL`` unless ``incoming_bytes`` more can be stored safely."""
        free = self.free_bytes()
        used = self.used_bytes() if self.settings.max_storage_bytes else None
        if not self._fits(free, used, max(0, incoming_bytes)):
            log.warning(
                "storage.pressure",
                free_mb=free // (1024 * 1024),
                used_mb=None if used is None else used // (1024 * 1024),
                incoming_mb=max(0, incoming_bytes) // (1024 * 1024),
            )
            raise AppError(
                ErrorCode.STORAGE_FULL,
                "The service is temporarily out of processing space. Please try again shortly.",
                retry_after=RETRY_AFTER_SECONDS,
            )

    def require_free_space(self) -> None:
        """Cheap floor-only check (one statvfs) for use inside a streaming write."""
        if self.free_bytes() < self.settings.min_free_disk_bytes:
            self.require()  # re-check with the full policy and raise with context


def _tree_size(root: Path) -> int:
    total = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue  # removed by cleanup while we walked
        except OSError:
            continue
    return total
