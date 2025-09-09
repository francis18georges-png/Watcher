import os
import pathlib
import subprocess
import time
from contextlib import ExitStack
from importlib import resources

_STACK = ExitStack()
_DATASETS: pathlib.Path | None = None


def _datasets_path() -> pathlib.Path:
    """Return the path to the datasets directory.

    If the environment variable ``WATCHER_DATASETS`` is set, its value is used.
    Otherwise we attempt to resolve the datasets location via
    :mod:`importlib.resources`.  This makes the path configurable while still
    supporting a sensible default.
    """

    env_path = os.environ.get("WATCHER_DATASETS")
    if env_path:
        return pathlib.Path(env_path)

    global _DATASETS
    if _DATASETS is None:
        try:
            root = _STACK.enter_context(resources.as_file(resources.files("datasets")))
            candidate = root / "python"
            if candidate.exists():
                _DATASETS = candidate
            else:
                raise FileNotFoundError
        except (ModuleNotFoundError, FileNotFoundError):
            _DATASETS = (
                pathlib.Path(__file__).resolve().parents[2] / "datasets" / "python"
            )

    return _DATASETS


DATASETS = _datasets_path()


def _run_pytest(task_dir: pathlib.Path, timeout: int = 60) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run(
            ["pytest", "-q"],
            cwd=str(task_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "pytest not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"pytest timed out after {timeout} seconds"}
    ok = p.returncode == 0
    return {
        "ok": ok,
        "sec": round(time.time() - t0, 3),
        "stdout": p.stdout[-4000:],
        "stderr": p.stderr[-4000:],
    }


def list_tasks(path: pathlib.Path | None = None) -> list[pathlib.Path]:
    base = path or _datasets_path()
    return [d for d in base.iterdir() if d.is_dir()]


def grade_task(name: str, path: pathlib.Path | None = None) -> dict:
    datasets = path or _datasets_path()
    task = datasets / name
    if not task.exists():
        return {"ok": False, "error": f"task {name} not found"}
    rep = _run_pytest(task)
    rep["score"] = 1.0 if rep.get("ok") else 0.0
    rep["task"] = name
    return rep


def grade_all() -> dict:
    results = [grade_task(p.name) for p in list_tasks()]
    ok = all(r.get("ok", False) for r in results) if results else False
    return {"ok": ok, "results": results}
