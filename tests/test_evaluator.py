import os
from pathlib import Path

from app.core.evaluator import QualityGate


def test_semgrep_config_path_is_absolute_when_run_from_subdir(monkeypatch):
    calls = []

    def fake_cmd(self, args):
        calls.append(args)
        return {"ok": True, "out": "", "err": ""}

    monkeypatch.setattr(QualityGate, "_cmd", fake_cmd)

    cwd = os.getcwd()
    try:
        os.chdir("app")
        gate = QualityGate()
        gate.run_all()
    finally:
        os.chdir(cwd)

    semgrep_args = next(args for args in calls if args and args[0] == "semgrep")
    cfg_path = semgrep_args[semgrep_args.index("--config") + 1]
    assert Path(cfg_path).is_absolute()
    assert Path(cfg_path).exists()
