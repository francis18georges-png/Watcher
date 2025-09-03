import subprocess
from pathlib import Path


class QualityGate:
    def run_all(self) -> dict:
        repo_root = Path(__file__).resolve().parents[2]
        semgrep_config = repo_root / "config" / "semgrep.yml"
        results = {
            "pytest": self._cmd(["pytest", "-q"]),
            "ruff": self._cmd(["ruff", "."]),
            "black": self._cmd(["black", "--check", "."]),
            "mypy": self._cmd(["mypy", "."]),
            "bandit": self._cmd(["bandit", "-q", "-r", "."]),
            "semgrep": self._cmd(
                [
                    "semgrep",
                    "--quiet",
                    "--error",
                    "--config",
                    str(semgrep_config),
                    ".",
                ]
            ),
        }
        ok = all(r["ok"] for r in results.values())
        return {"ok": ok, "results": results}

    def _cmd(self, args: list[str]) -> dict:
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=60)
            return {
                "ok": p.returncode == 0,
                "out": p.stdout[-4000:],
                "err": p.stderr[-4000:],
            }
        except Exception as e:  # pragma: no cover - defensive
            return {"ok": False, "err": str(e), "out": ""}
