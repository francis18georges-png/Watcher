"""End-to-end smoke tests executed in offline mode."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.e2e_offline
def test_cli_run_offline(tmp_path):
    """`watcher run --offline` returns the deterministic fallback response."""

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["WATCHER_PATHS__BASE_DIR"] = str(tmp_path)
    env["WATCHER_MEMORY__DB_PATH"] = "memory/e2e.db"
    env["WATCHER_INTELLIGENCE__MODE"] = "offline"

    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "run", "--offline", "--prompt", "Ping?"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    stdout = result.stdout.strip()
    expected = "Voici quelques détails supplémentaires., manque de politesse"
    assert stdout in {expected, f"Echo: Ping?"}
