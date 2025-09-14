"""Simple data preparation pipeline."""

from __future__ import annotations

from pathlib import Path
import json
import logging
import time
import statistics
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

from app.config import load_config

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "datasets" / "raw"
PROCESSED_DIR = BASE_DIR / "datasets" / "processed"


def load_raw_data(path: Path | str | None = None) -> dict | list[dict]:
    """Load and validate raw data from ``datasets/raw``.

    The function ensures the file or directory exists and uses a ``.json``
    extension before reading.  When *path* points to a directory all ``.json``
    files inside are loaded and returned as a list of dictionaries.
    """

    p = Path(path) if path else RAW_DIR / "data.json"
    if not p.exists():
        logging.error("raw data file '%s' does not exist", p)
        raise FileNotFoundError(p)
    if p.is_dir():
        data: list[dict] = []
        for file in sorted(p.glob("*.json")):
            try:
                with file.open("r", encoding="utf-8") as fh:
                    data.append(json.load(fh))
            except json.JSONDecodeError:
                logging.exception("raw data file '%s' contains invalid JSON", file)
                raise
        return data
    if p.suffix.lower() != ".json":
        logging.error("raw data file '%s' has unsupported format", p)
        raise ValueError(f"unsupported file format: {p}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        logging.exception("raw data file '%s' contains invalid JSON", p)
        raise exc


def _remove_numeric_outliers(
    values: list[float], threshold: float = 3.5
) -> list[float]:
    """Return *values* stripped of statistical outliers.

    Uses the median absolute deviation (MAD) method with a configurable
    *threshold*. Values whose modified z-score exceeds the threshold are
    considered outliers and removed.
    """

    if len(values) < 2:
        return values
    median = statistics.median(values)
    mad = statistics.median([abs(x - median) for x in values])
    if mad == 0:
        return values
    result: list[float] = []
    for x in values:
        z = 0.6745 * (x - median) / mad
        if abs(z) <= threshold:
            result.append(x)
    return result


def normalize_data(data: dict) -> dict:
    """Normalize *data* values and remove duplicates/outliers.

    - Strings are stripped of surrounding whitespace.
    - Lists are deduplicated while preserving order.
    - Numerical lists additionally have statistical outliers removed.
    """

    normalized: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            normalized[key] = value.strip()
            continue
        if isinstance(value, list):
            seen: set[Any] = set()
            deduped: list[Any] = []
            for item in value:
                item_norm = item.strip() if isinstance(item, str) else item
                if item_norm not in seen:
                    seen.add(item_norm)
                    deduped.append(item_norm)
            if deduped and all(isinstance(x, (int, float)) for x in deduped):
                cleaned = _remove_numeric_outliers([float(x) for x in deduped])
                normalized[key] = [int(x) if x.is_integer() else x for x in cleaned]
            else:
                normalized[key] = deduped
            continue
        normalized[key] = value
    return normalized


def clean_data(data: dict) -> dict:
    """Remove falsy values from *data*."""
    return {k: v for k, v in data.items() if v}


def transform_data(
    data: dict | Iterable[dict], filename: str = "cleaned.json"
) -> Path | list[Path]:
    """Persist cleaned *data* into ``datasets/processed``.

    When *data* is an iterable of dictionaries each element is written to a
    separate file using the pattern ``{index}_<filename>``.  This groups writes
    to minimise filesystem overhead when persisting multiple records.

    Parameters
    ----------
    data:
        Cleaned data to save or an iterable of multiple data items.
    filename:
        Name of the JSON file to create in the processed directory. When
        writing multiple items the name is used as a suffix.

    Returns
    -------
    pathlib.Path | list[pathlib.Path]
        The path(s) to the written file(s).
    """

    dest_dir = PROCESSED_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(data, Iterable) and not isinstance(data, dict):
        paths: list[Path] = []
        for idx, item in enumerate(data):
            dest = dest_dir / f"{idx}_{filename}"
            with dest.open("w", encoding="utf-8") as fh:
                json.dump(item, fh, ensure_ascii=False, indent=2)
            paths.append(dest)
        return paths

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

    # Prefetch step callables to group module lookups and avoid repeated
    # resolution during execution.
    resolved_steps = [(name, _resolve_step(path)) for name, path in steps_cfg.items()]

    result: Any = data
    for name, step in resolved_steps:
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
