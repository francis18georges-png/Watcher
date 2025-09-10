try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fallback
    import numpy_stub as np  # type: ignore

__all__ = ["np"]
