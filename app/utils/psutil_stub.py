"""Minimal psutil replacement used when the third-party dependency is absent."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterator

__all__ = [
    "STUB_CPU_PERCENT",
    "STUB_MEMORY_TOTAL",
    "STUB_MEMORY_AVAILABLE",
    "STUB_MEMORY_USED",
    "STUB_MEMORY_PERCENT",
    "cpu_percent",
    "virtual_memory",
    "Process",
    "process_iter",
]

# Deterministic values exposed for tests that rely on predictable metrics.
STUB_CPU_PERCENT: float = 12.5
STUB_MEMORY_TOTAL: int = 8 * 1024 * 1024 * 1024
STUB_MEMORY_AVAILABLE: int = 5 * 1024 * 1024 * 1024
STUB_MEMORY_USED: int = STUB_MEMORY_TOTAL - STUB_MEMORY_AVAILABLE
STUB_MEMORY_PERCENT: float = round((STUB_MEMORY_USED / STUB_MEMORY_TOTAL) * 100.0, 1)


@dataclass(frozen=True)
class _VirtualMemory:
    """Subset of :func:`psutil.virtual_memory` result used by Watcher."""

    total: int
    available: int
    percent: float
    used: int
    free: int


@dataclass(frozen=True)
class _ProcessMemoryInfo:
    """Lightweight stand-in for :class:`psutil.Process` memory info."""

    rss: int
    vms: int


class Process:
    """Simplified representation of :class:`psutil.Process`."""

    def __init__(self, pid: int | None = None) -> None:
        self.pid = pid if pid is not None else os.getpid()

    def cpu_percent(self, interval: float | None = None) -> float:
        """Return the deterministic CPU percentage used by the stub."""

        return STUB_CPU_PERCENT

    def memory_info(self) -> _ProcessMemoryInfo:
        """Return fake RSS/VMS metrics mimicking :mod:`psutil`."""

        return _ProcessMemoryInfo(rss=STUB_MEMORY_USED, vms=STUB_MEMORY_USED)

    def num_threads(self) -> int:
        return 1

    def name(self) -> str:
        return "watcher"


def cpu_percent(interval: float | None = None) -> float:
    """Return the deterministic CPU percentage used by tests."""

    return STUB_CPU_PERCENT


def virtual_memory() -> _VirtualMemory:
    """Return predictable virtual memory information."""

    return _VirtualMemory(
        total=STUB_MEMORY_TOTAL,
        available=STUB_MEMORY_AVAILABLE,
        percent=STUB_MEMORY_PERCENT,
        used=STUB_MEMORY_USED,
        free=STUB_MEMORY_AVAILABLE,
    )


def process_iter(attrs: tuple[str, ...] | None = None) -> Iterator[Process]:  # noqa: ARG001
    """Yield a single stub :class:`Process` instance.

    The real :func:`psutil.process_iter` returns an iterator over running
    processes. The stub only needs to provide enough structure for tests that
    inspect the currently running process.
    """

    yield Process()
