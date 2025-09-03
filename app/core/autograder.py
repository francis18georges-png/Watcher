import pathlib
import time

from app.core import sandbox


DATASETS = pathlib.Path("datasets/python")


def _run_pytest(task_dir: pathlib.Path, timeout: int = 60) -> dict:
    t0 = time.time()
    p = sandbox.run(["pytest", "-q"], cwd=str(task_dir), timeout=timeout)
    ok = p["code"] == 0
    return {
        "ok": ok,
        "code": p["code"],
        "sec": round(time.time() - t0, 3),
        "stdout": p["out"][-4000:],
        "stderr": p["err"][-4000:],
    }


def list_tasks() -> list[pathlib.Path]:
    return [d for d in DATASETS.iterdir() if d.is_dir()]


def grade_task(name: str) -> dict:
    root = DATASETS.resolve()
    safe_name = pathlib.Path(name).name
    task = (root / safe_name).resolve()
    if not task.is_relative_to(root) or not task.exists():
        return {"ok": False, "error": f"task {safe_name} not found"}
    rep = _run_pytest(task)
    rep["score"] = 1.0 if rep["ok"] else 0.0
    rep["task"] = safe_name
    return rep


def grade_all() -> dict:
    results = [grade_task(p.name) for p in list_tasks()]
    ok = all(r.get("ok", False) for r in results) if results else False
    return {"ok": ok, "results": results}
