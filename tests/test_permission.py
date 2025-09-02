"""Tests for the Engine._ask_permission helper."""

from pathlib import Path
import sys
import types

# Ensure repository root is on the import path
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Provide a light-weight stub for numpy to avoid heavy dependency during tests
sys.modules.setdefault("numpy", types.ModuleType("numpy"))

from app.core.engine import Engine


def test_ask_permission_creates_directory_and_persists_answer(tmp_path, monkeypatch):
    """_ask_permission should persist the answer and create parent dirs."""

    # Instantiate Engine without triggering _bootstrap
    engine = Engine.__new__(Engine)

    consent_file = tmp_path / "perm" / "consent.txt"

    # Simulate user answering "y"
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert engine._ask_permission("Proceed?", consent_file) is True

    # Directory and file should now exist with the stored answer
    assert consent_file.parent.is_dir()
    assert consent_file.read_text() == "y"

    # Second call should reuse the stored value without prompting
    def _fail_prompt(_: str) -> str:  # pragma: no cover - should not be called
        raise AssertionError("input() was called again")

    monkeypatch.setattr("builtins.input", _fail_prompt)
    assert engine._ask_permission("Proceed?", consent_file) is True
