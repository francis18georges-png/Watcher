"""Lightweight stub implementation of a subset of NumPy used for tests.

This module provides just enough functionality for the project without
requiring the real ``numpy`` dependency, which may be unavailable in
restricted environments.
"""

from __future__ import annotations

import math
import struct
from typing import Iterable, List

float32 = "float32"


class ndarray:
    """Minimal array type supporting required NumPy operations."""

    def __init__(self, values: Iterable[float]):
        self._values = [float(v) for v in values]

    def astype(self, _dtype: str) -> "ndarray":
        return self

    def tobytes(self) -> bytes:
        return struct.pack(f"{len(self._values)}f", *self._values)

    def __matmul__(self, other: "ndarray") -> float:
        return sum(a * b for a, b in zip(self._values, other._values))

    @property
    def size(self) -> int:  # pragma: no cover - trivial
        return len(self._values)

    def __iter__(self):  # pragma: no cover - convenience
        return iter(self._values)

    def tolist(self) -> List[float]:  # pragma: no cover - convenience
        return list(self._values)


def array(values: Iterable[float], dtype: str | None = None) -> ndarray:  # noqa: ARG001
    return ndarray(values)


def frombuffer(buf: bytes, dtype: str | None = None) -> ndarray:  # noqa: ARG001
    count = len(buf) // 4
    return ndarray(struct.unpack(f"{count}f", buf))


class _Linalg:
    @staticmethod
    def norm(vec: Iterable[float]) -> float:
        return math.sqrt(sum(v * v for v in vec))


linalg = _Linalg()
