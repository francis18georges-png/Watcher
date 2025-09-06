import pathlib
import subprocess
import time

from app.core.validation import validate_dataset

DATASETS = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "python"


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


def list_tasks() -> list[pathlib.Path]:
    tasks: list[pathlib.Path] = []
    for d in DATASETS.iterdir():
        if not d.is_dir():
            continue
        try:
            validate_dataset(d)
        except ValueError:
            continue
        tasks.append(d)
    return tasks


def grade_task(name: str) -> dict:
    task = DATASETS / name
    try:
        validate_dataset(task)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    rep = _run_pytest(task)
    rep["score"] = 1.0 if rep.get("ok") else 0.0
    rep["task"] = name
    return rep


def grade_all() -> dict:
    results = [grade_task(p.name) for p in list_tasks()]
    ok = all(r.get("ok", False) for r in results) if results else False
    return {"ok": ok, "results": results}
