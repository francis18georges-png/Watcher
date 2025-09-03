import subprocess

from app.config import load_settings


class QualityGate:
    def __init__(self) -> None:
        self.settings = load_settings()

    def run_all(self) -> dict:
        dev = self.settings.get("dev", {})
        timeout = dev.get("test_timeout_sec", 60)
        semgrep_cfg = dev.get("semgrep_ruleset", "config/semgrep.yml")
        results = {
            "pytest": self._cmd(["pytest", "-q"], timeout),
            "ruff": self._cmd(["ruff", "."], timeout),
            "black": self._cmd(["black", "--check", "."], timeout),
            "mypy": self._cmd(["mypy", "."], timeout),
            "bandit": self._cmd(["bandit", "-q", "-r", "."], timeout),
            "semgrep": self._cmd(
                [
                    "semgrep",
                    "--quiet",
                    "--error",
                    "--config",
                    semgrep_cfg,
                    ".",
                ],
                timeout,
            ),
        }
        ok = all(r["ok"] for r in results.values())
        return {"ok": ok, "results": results}

    def _cmd(self, args: list[str], timeout: int) -> dict:
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return {
                "ok": p.returncode == 0,
                "out": p.stdout[-4000:],
                "err": p.stderr[-4000:],
            }
        except Exception as e:  # pragma: no cover - defensive
            return {"ok": False, "err": str(e), "out": ""}
