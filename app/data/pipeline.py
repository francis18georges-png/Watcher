"""Simple data preparation pipeline."""

from __future__ import annotations

from pathlib import Path
import json
import logging
import time
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Protocol, runtime_checkable

from app.config import load_config

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "datasets" / "raw"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"


def load_raw_data(path: Path | str | None = None) -> dict:
    """Load raw data from ``datasets/raw``.

    Parameters
    ----------
    path:
        Optional path to a JSON file. If not provided, ``RAW_DIR / 'data.json'``
        is used.

    Returns
    -------
    dict
        The parsed JSON content. An empty dictionary is returned when the file
        does not exist.
    """
    p = Path(path) if path else RAW_DIR / "data.json"
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def clean_data(data: dict) -> dict:
    """Remove falsy values from *data*."""
    return {k: v for k, v in data.items() if v}


def transform_data(data: dict, filename: str = "cleaned.json") -> Path:
    """Persist cleaned *data* into ``datasets/processed``.

    Parameters
    ----------
    data:
        Cleaned data to save.
    filename:
        Name of the JSON file to create in the processed directory.

    Returns
    -------
    pathlib.Path
        The path to the written file.
    """
    dest_dir = PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return dest


@runtime_checkable
class PipelineStep(Protocol):
    """Simple interface for pipeline steps.

    A pipeline step is any callable that accepts an arbitrary input and
    returns an arbitrary output. Steps are executed sequentially where the
    return value of one step is passed as the argument to the next.
    """

    def __call__(self, data: Any) -> Any:  # pragma: no cover - Protocol definition
        ...


def _resolve_step(path: str) -> PipelineStep:
    """Import and instantiate the step defined by *path*.

    Parameters
    ----------
    path:
        Dotted path to a callable implementing :class:`PipelineStep`.

    Returns
    -------
    PipelineStep
        The instantiated pipeline step.
    """

    module_name, _, attr = path.rpartition(".")
    module = import_module(module_name)
    obj = getattr(module, attr)
    step = obj() if isinstance(obj, type) else obj
    if not isinstance(step, PipelineStep):  # pragma: no cover - defensive
        raise TypeError(f"{path} is not a PipelineStep")
    return step

@dataclass
class StepResult:
    """Execution details for a pipeline step."""

    name: str
    duration: float
    success: bool


Hook = Callable[[StepResult], None]


def run_pipeline(data: Any | None = None, hooks: list[Hook] | None = None) -> Any:
    """Execute configured data pipeline steps.

    Steps are declared in ``config/settings.toml`` under ``[data.steps]`` as a
    mapping where the values are dotted import paths. They are executed in the
    order they are declared in the configuration.  Each step is timed and hooks
    are invoked with a :class:`StepResult` object.

    Parameters
    ----------
    data:
        Initial data passed to the first pipeline step. Defaults to ``None``.
    hooks:
        Optional list of callables invoked after each step. They receive a
        :class:`StepResult` instance. Exceptions raised by hooks are logged and
        ignored.

    Returns
    -------
    Any
        The result returned by the last pipeline step.
    """

    cfg = load_config("data")
    steps_cfg = cfg.get("steps", {})
    result: Any = data
    for name, path in steps_cfg.items():
        step = _resolve_step(path)
        start = time.perf_counter()
        ok = True
        try:
            result = step(result)
        except Exception:  # pragma: no cover - best effort
            ok = False
            logging.exception("pipeline step '%s' failed", name)
            raise
        finally:
            duration = time.perf_counter() - start
            if hooks:
                sr = StepResult(name, duration, ok)
                for hook in hooks:
                    try:
                        hook(sr)
                    except Exception:  # pragma: no cover - defensive
                        logging.exception("pipeline hook failed")
    return result
