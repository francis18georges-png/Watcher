import ast
import operator as op
import re
from typing import Any

# Supported operators mapped to functions
_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}

# Regex matching a numeric literal. Supports optional leading sign and
# scientific notation (e.g. ``+1.0`` or ``1e-3``).
_NUMBER_PATTERN = r"""
    [+-]?                    # optional sign
    (?:
        (?:\d+(?:\.\d*)?) # digits with optional decimal part
        |(?:\.\d+)          # or decimal without leading digits
    )
    (?:[eE][+-]?\d+)?       # optional exponent
"""

# Token pattern for validating expressions. Permits numbers and basic
# arithmetic operators/parentheses.
_TOKEN_RE = re.compile(
    rf"""
    \s*
    (?:{_NUMBER_PATTERN}|[+\-*/()])
    """,
    re.VERBOSE,
)


def _validate(expr: str) -> None:
    """Validate that *expr* contains only supported tokens."""
    expr = expr.strip()
    pos = 0
    while pos < len(expr):
        match = _TOKEN_RE.match(expr, pos)
        if not match:
            raise ValueError("Malformed expression")
        pos = match.end()
    if pos != len(expr):
        raise ValueError("Malformed expression")


def safe_eval(expr: str) -> Any:
    """Safely evaluate a mathematical expression.

    Only numeric literals and basic arithmetic operators are permitted.
    A :class:`ValueError` is raised for any malformed or unsupported
    expression.
    """
    _validate(expr)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - handled uniformly
        raise ValueError("Malformed expression") from exc

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Unsupported constant type")
        if isinstance(node, ast.BinOp):
            operator_fn = _OPERATORS.get(type(node.op))
            if operator_fn is None:
                raise ValueError("Unsupported operator")
            return operator_fn(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            operator_fn = _OPERATORS.get(type(node.op))
            if operator_fn is None:
                raise ValueError("Unsupported operator")
            return operator_fn(_eval(node.operand))
        raise ValueError("Unsupported expression")

    return _eval(tree)
