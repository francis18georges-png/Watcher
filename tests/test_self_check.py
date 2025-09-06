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


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("0.1 + 0.2", 0.3),
        ("1 / 3", 1 / 3),
    ],
)
def test_safe_eval_handles_float_results(expr, expected):
    """Ensure floating point math is evaluated with appropriate tolerance."""
    assert abs(safe_eval(expr) - expected) < 1e-9


@pytest.mark.parametrize(
    "expr, wrong",
    [
        ("0.1 + 0.2", 0.3001),
        ("1 / 3", 0.333),
    ],
)
def test_safe_eval_detects_incorrect_float_results(expr, wrong):
    """Incorrect answers should not match even within tight tolerance."""
    result = safe_eval(expr)
    assert abs(result - wrong) > 1e-5
