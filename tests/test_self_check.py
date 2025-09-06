import pytest

from app.core.self_check import safe_eval


def test_safe_eval_valid_expression():
    assert safe_eval("2 + 3 * 4") == 14


def test_safe_eval_rejects_malformed():
    with pytest.raises(ValueError):
        safe_eval("2 + ")


def test_safe_eval_prevents_code_execution(tmp_path, monkeypatch):
    # Attempt to execute arbitrary code via import should raise ValueError
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('echo unsafe')")
