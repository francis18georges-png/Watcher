import pytest

from app.core.self_check import analyze


@pytest.mark.parametrize(
    "expr, answer, expected",
    [
        ("5 - 3", "2", True),
        ("5 - 3", "1", False),
        ("4 * -2", "-8", True),
        ("4 * -2", "8", False),
        ("6 / 4", "1.5", True),
        ("6 / 4", "1.4", False),
        ("-6 / 4", "-1.5", True),
        ("-6 / 4", "1.5", False),
    ],
)
def test_analyze(expr: str, answer: str, expected: bool) -> None:
    """Verify that :func:`analyze` correctly evaluates simple arithmetic."""

    assert analyze(expr, answer) is expected
