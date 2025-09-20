"""Minimal psutil stub used for offline testing."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Iterable

try:  # pragma: no cover - resource may be missing on non-Unix
    import resource
except ImportError:  # pragma: no cover - fallback for platforms without resource
    resource = None  # type: ignore[assignment]


class Error(Exception):
    """Base class for psutil errors."""


class NoSuchProcess(Error):
    """Raised when a process identifier cannot be resolved."""


class AccessDenied(Error):
    """Raised when process information is not accessible."""


@dataclass
class _MemoryInfo:
    rss: int


class Process:
    """Very small subset of :class:`psutil.Process`."""

    def __init__(self, pid: int | None = None) -> None:
        self.pid = int(pid) if pid is not None else os.getpid()
        if self.pid != os.getpid():
            raise NoSuchProcess(self.pid)
        self._last_time = time.process_time()
        self.info: dict[str, str] = {}

    def is_running(self) -> bool:
        return self.pid == os.getpid()

    def cpu_percent(self, interval: float | None = None) -> float:
        now = time.process_time()
        diff = max(now - self._last_time, 0.0)
        self._last_time = now
        return diff * 100.0

    def memory_info(self) -> _MemoryInfo:
        if resource is None:
            rss = 0
        else:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss = usage.ru_maxrss
            if sys.platform != "darwin":  # on mac already bytes
                rss *= 1024
        return _MemoryInfo(rss=rss)


def process_iter(attrs: Iterable[str] | None = None):
    proc = Process(os.getpid())
    info: dict[str, str] = {}
    if attrs and "name" in attrs:
        info["name"] = os.path.basename(sys.argv[0]) or "python"
    proc.info = info
    yield proc


__all__ = [
    "AccessDenied",
    "Error",
    "NoSuchProcess",
    "Process",
    "process_iter",
]
