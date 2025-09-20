from __future__ import annotations

import os
import random

from app import cli
from app.core.reproducibility import set_seed
from app.utils import np

HAS_NUMPY_RNG = hasattr(np, "random") and hasattr(np.random, "rand")


def test_set_seed_reproducible():
    set_seed(123)
    py_vals = [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        np_vals = np.random.rand(3)

    set_seed(123)
    assert py_vals == [random.random() for _ in range(3)]
    if HAS_NUMPY_RNG:
        assert np.allclose(np_vals, np.random.rand(3))


def _run_cli_and_sample(args: list[str]) -> tuple[str | None, list[float]]:
    random.seed(999)
    exit_code = cli.main(args)
    assert exit_code == 0
    return os.environ.get("PYTHONHASHSEED"), [random.random() for _ in range(3)]


def test_cli_reproducibility_end_to_end(monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    env_seed, seq1 = _run_cli_and_sample(["plugin", "list"])
    assert env_seed == "42"

    env_seed_repeat, seq2 = _run_cli_and_sample(["plugin", "list"])
    assert env_seed_repeat == "42"
    assert seq1 == seq2

    env_seed_custom, seq_custom1 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_seed_custom == "123"

    env_seed_custom_repeat, seq_custom2 = _run_cli_and_sample([
        "--seed",
        "123",
        "plugin",
        "list",
    ])
    assert env_seed_custom_repeat == "123"
    assert seq_custom1 == seq_custom2
