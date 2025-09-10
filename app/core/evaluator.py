import subprocess
from typing import TypedDict


class CommandResult(TypedDict):
    ok: bool
    out: str
    err: str


class QualityGate:
    def run_all(self) -> dict[str, CommandResult]:
        results: dict[str, CommandResult] = {
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
                    "config/semgrep.yml",
                    ".",
                ]
            ),
        }
        return results

    def _cmd(self, args: list[str]) -> CommandResult:
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=60)
            return {
                "ok": p.returncode == 0,
                "out": p.stdout[-4000:],
                "err": p.stderr[-4000:],
            }
        except FileNotFoundError as e:
            return {"ok": False, "err": f"{args[0]} introuvable: {e}", "out": ""}
        except Exception as e:  # pragma: no cover - defensive
            return {"ok": False, "err": str(e), "out": ""}
