"""Process-wide, non-queuing admission for synchronous Web Read work."""

import asyncio
import errno
import shutil
import sys
import tempfile
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import anyio
import psutil

from web_search.limits import (
    MAX_ACTIVE_WORK,
    MAX_BROWSER_SESSIONS,
    MAX_BROWSER_TEMPORARY_BYTES,
    MAX_PROCESS_TREE_RSS,
    MAX_RETAINED_BYTES,
    MAX_STATE_BYTES,
    MAX_TEMPORARY_BYTES,
    WORK_MEMORY_BYTES,
    WORK_TEMPORARY_BYTES,
)


class ResourceExhausted(OSError):
    def __init__(self) -> None:
        super().__init__(errno.ENOSPC, "Web Read resource reservation was exhausted.")


def process_tree_rss() -> int:
    root = psutil.Process()
    total = root.memory_info().rss
    for child in root.children(recursive=True):
        try:
            total += child.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return total


def system_capacity(directory: Path) -> tuple[int, int, int]:
    while not directory.exists():
        directory = directory.parent
    return psutil.virtual_memory().available, process_tree_rss(), shutil.disk_usage(directory).free


def retained_size(value: Any) -> int:
    """Count owned Python objects once; browser/native allocations have separate limits."""
    seen: set[int] = set()
    pending = [value]
    total = 0
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        total += sys.getsizeof(current)
        if isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
        elif isinstance(current, list | tuple | set | frozenset):
            pending.extend(current)
        elif is_dataclass(current) and not isinstance(current, type):
            pending.extend(
                getattr(current, item.name)
                for item in fields(current)
                if item.name not in {"browser", "interaction_lock"}
            )
        if total > MAX_STATE_BYTES:
            raise ResourceExhausted
    return total


@dataclass(eq=False)
class WorkLease:
    remaining: int = WORK_TEMPORARY_BYTES
    files: set[Path] = field(default_factory=set)
    read_id: str | None = None


CURRENT_WORK: ContextVar[WorkLease | None] = ContextVar("web_read_work", default=None)


async def run_blocking[T](function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Keep the admission lease and state lock until already-started native work exits."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        with anyio.CancelScope(shield=True):
            try:
                await asyncio.shield(task)
            except Exception:
                pass
        raise


async def monitor_worker(pid: int) -> None:
    while True:
        try:
            if psutil.Process(pid).memory_info().rss > WORK_MEMORY_BYTES:
                raise ResourceExhausted
        except psutil.NoSuchProcess:
            return
        await asyncio.sleep(0.05)


class AdmissionController:
    def __init__(
        self,
        *,
        max_active: int = MAX_ACTIVE_WORK,
        max_temporary_bytes: int = MAX_TEMPORARY_BYTES,
        max_retained_bytes: int = MAX_RETAINED_BYTES,
        capacity: Callable[[Path], tuple[int, int, int]] = system_capacity,
    ) -> None:
        self._max_active = max_active
        self._max_temporary_bytes = max_temporary_bytes
        self._max_retained_bytes = max_retained_bytes
        self._capacity = capacity
        self._leases: set[WorkLease] = set()
        self._files: dict[Path, int] = {}
        self._states: dict[str, int] = {}
        self._browsers: dict[Path, tempfile.TemporaryDirectory[str]] = {}
        self._lock = Lock()

    def acquire(self, directory: Path | None) -> WorkLease | None:
        with self._lock:
            if len(self._leases) >= self._max_active:
                return None
            if sum(self._states.values()) + (len(self._leases) + 1) * MAX_STATE_BYTES > (
                self._max_retained_bytes
            ):
                return None
            reserved_disk = sum(lease.remaining for lease in self._leases)
            if (
                sum(self._files.values())
                + len(self._browsers) * MAX_BROWSER_TEMPORARY_BYTES
                + reserved_disk
                + WORK_TEMPORARY_BYTES
            ) > (self._max_temporary_bytes):
                return None
            try:
                available, rss, disk_free = self._capacity(directory or Path(tempfile.gettempdir()))
            except (OSError, psutil.Error):
                return None
            memory_reservation = (len(self._leases) + 1) * WORK_MEMORY_BYTES
            if (
                available < memory_reservation
                or rss + memory_reservation > MAX_PROCESS_TREE_RSS
                or disk_free < reserved_disk + WORK_TEMPORARY_BYTES
            ):
                return None
            lease = WorkLease()
            self._leases.add(lease)
            return lease

    def release(self, lease: WorkLease) -> None:
        with self._lock:
            self._leases.remove(lease)

    def retain(self, read_id: str, size: int) -> None:
        with self._lock:
            total = sum(self._states.values()) - self._states.get(read_id, 0) + size
            if size > MAX_STATE_BYTES or total > self._max_retained_bytes:
                raise ResourceExhausted
            self._states[read_id] = size

    def forget(self, read_id: str) -> None:
        with self._lock:
            self._states.pop(read_id, None)

    def browser_directory(self, directory: Path | None) -> Path:
        lease = CURRENT_WORK.get()
        if lease is None:
            raise ResourceExhausted
        with self._lock:
            if len(self._browsers) >= MAX_BROWSER_SESSIONS or (
                lease.remaining < MAX_BROWSER_TEMPORARY_BYTES
            ):
                raise ResourceExhausted
            if directory is not None:
                directory.mkdir(parents=True, exist_ok=True)
            temporary = tempfile.TemporaryDirectory(prefix="web-read-browser-", dir=directory)
            path = Path(temporary.name)
            self._browsers[path] = temporary
            lease.remaining -= MAX_BROWSER_TEMPORARY_BYTES
            return path

    def remove_browser(self, path: Path) -> None:
        with self._lock:
            temporary = self._browsers.get(path)
            if temporary is not None:
                temporary.cleanup()
                del self._browsers[path]

    def write(self, data: bytes, directory: Path | None, suffix: str) -> Path:
        lease = CURRENT_WORK.get()
        if lease is None:
            raise ResourceExhausted
        with self._lock:
            if len(data) > lease.remaining:
                raise ResourceExhausted
            lease.remaining -= len(data)
        path: Path | None = None
        try:
            if directory is not None:
                directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix="web-read-", suffix=suffix, dir=directory, delete=False
            ) as artifact:
                path = Path(artifact.name)
                artifact.write(data)
            with self._lock:
                self._files[path] = len(data)
                lease.files.add(path)
            return path
        except BaseException:
            if path is not None:
                path.unlink(missing_ok=True)
            with self._lock:
                lease.remaining += len(data)
            raise

    def remove(self, path: Path | None) -> None:
        if path is None:
            return
        path.unlink(missing_ok=True)
        with self._lock:
            size = self._files.pop(path, 0)
            lease = CURRENT_WORK.get()
            if lease is not None and path in lease.files:
                lease.remaining += size
                lease.files.remove(path)


PROCESS_ADMISSION = AdmissionController()
