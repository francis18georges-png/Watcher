"""Shared helpers for lightweight data scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_params(path: str | Path) -> dict[str, Any]:
    """Load parameters from a JSON-formatted YAML file.

    The repository stores ``params.yaml`` using JSON syntax so that the
    configuration can be parsed without external dependencies.  This helper
    wraps the reading and provides basic validation to ensure a mapping is
    returned.
    """

    params_path = Path(path)
    if not params_path.exists():
        raise FileNotFoundError(f"Parameter file not found: {params_path}")

    try:
        data = json.loads(params_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
        raise ValueError(
            f"Unable to parse parameters in {params_path}. Ensure it contains valid JSON."
        ) from exc

    if not isinstance(data, dict):  # pragma: no cover - defensive path
        raise ValueError("Parameter file must contain a top-level object")

    return data


def get_nested(params: Mapping[str, Any], keys: list[str]) -> Any:
    """Retrieve a nested parameter value given a list of keys."""

    current: Any = params
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, Mapping) or key not in current:
            joined = "/".join(traversed)
            raise KeyError(f"Missing parameter path: {joined}")
        current = current[key]
    return current
