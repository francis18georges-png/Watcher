from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import textwrap
from pathlib import Path
from string import Template
from typing import Any

from app import cli
from app.core.reproducibility import set_seed
from app.utils import np

HAS_NUMPY_RNG = hasattr(np, "random") and hasattr(np.random, "rand")

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_set_seed_reproducible():
    set_seed(123)
    py_vals = [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        np_vals = np.random.rand(3)

    set_seed(123)
    assert py_vals == [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        assert np.allclose(np_vals, np.random.rand(3))


def _run_cli_and_sample(args: list[str]) -> tuple[dict[str, str | None], list[float]]:
    random.seed(999)
    exit_code = cli.main(args)
    assert exit_code == 0
    env_values = {
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "WATCHER_TRAINING__SEED": os.environ.get("WATCHER_TRAINING__SEED"),
    }
    return env_values, [random.random() for _ in range(3)]


def _run_cli_subprocess(
    args: list[str],
) -> tuple[dict[str, str | None], list[str], list[float]]:
    template = Template(
        """
import json
import os
import random
from app import cli

random.seed(999)
args = $ARGS
exit_code = cli.main(args)
payload = {
    "exit_code": exit_code,
    "env": {
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "WATCHER_TRAINING__SEED": os.environ.get("WATCHER_TRAINING__SEED"),
    },
    "sequence": [random.random() for _ in range(3)],
}
print(json.dumps(payload))
"""
    )
    script = textwrap.dedent(template.substitute(ARGS=repr(args)))
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env.pop("WATCHER_TRAINING__SEED", None)
    pythonpath = env.get("PYTHONPATH")
    repo_root = str(REPO_ROOT)
    env["PYTHONPATH"] = (
        repo_root if not pythonpath else f"{repo_root}{os.pathsep}{pythonpath}"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=True,
        text=True,
        env=env,
    )
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert stdout_lines, "CLI invocation produced no output"
    payload: dict[str, Any] = json.loads(stdout_lines[-1])
    assert payload["exit_code"] == 0
    env_values = {
        key: (value if value is None else str(value))
        for key, value in payload["env"].items()
    }
    sequence = [float(value) for value in payload["sequence"]]
    return env_values, stdout_lines[:-1], sequence


def test_cli_reproducibility_end_to_end(monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("WATCHER_TRAINING__SEED", "0")

    env_values, seq1 = _run_cli_and_sample(["plugin", "list"])
    assert env_values == {
        "PYTHONHASHSEED": "42",
        "WATCHER_TRAINING__SEED": "42",
    }

    env_values_repeat, seq2 = _run_cli_and_sample(["plugin", "list"])
    assert env_values_repeat == env_values
    assert seq1 == seq2

    env_custom, seq_custom1 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom == {
        "PYTHONHASHSEED": "123",
        "WATCHER_TRAINING__SEED": "123",
    }

    env_custom_repeat, seq_custom2 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom_repeat == env_custom
    assert seq_custom1 == seq_custom2


def test_cli_reproducibility_via_subprocess():
    env_values, output_lines, seq1 = _run_cli_subprocess(["plugin", "list"])
    assert env_values == {
        "PYTHONHASHSEED": "42",
        "WATCHER_TRAINING__SEED": "42",
    }
    assert output_lines, "plugin listing should produce output"

    env_repeat, output_repeat, seq2 = _run_cli_subprocess(["plugin", "list"])
    assert env_repeat == env_values
    assert output_repeat == output_lines
    assert seq2 == seq1

    env_custom, output_custom, seq_custom1 = _run_cli_subprocess([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom == {
        "PYTHONHASHSEED": "123",
        "WATCHER_TRAINING__SEED": "123",
    }
    assert output_custom == output_lines
    assert seq_custom1 != seq1

    env_custom_repeat, output_custom_repeat, seq_custom2 = _run_cli_subprocess([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_custom_repeat == env_custom
    assert output_custom_repeat == output_custom
    assert seq_custom2 == seq_custom1
