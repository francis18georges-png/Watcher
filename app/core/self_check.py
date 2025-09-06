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

def safe_eval(expr: str) -> Any:
    """Safely evaluate a mathematical expression.

    Only numeric literals and basic arithmetic operators are permitted.
    A :class:`ValueError` is raised for any malformed or unsupported
    expression.
    """
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


def analyze(text: str) -> dict[str, list[float] | float | None]:
    """Extract numeric tokens from ``text`` and evaluate them.

    The function searches for substrings containing digits and basic
    arithmetic operators. Each token is evaluated with :func:`safe_eval` and
    collected in order of appearance. The last successfully evaluated number
    is returned as ``answer``. When no tokens can be evaluated ``answer`` is
    ``None``.
    """

    tokens = re.findall(r"[\d\s\.\+\-\*/]+", text)
    numbers: list[float] = []

    for token in tokens:
        token = token.strip()
        if not token or not re.search(r"\d", token):
            continue
        try:
            value = safe_eval(token)
        except ValueError:
            continue
        if isinstance(value, (int, float)):
            numbers.append(float(value))

    return {"numbers": numbers, "answer": numbers[-1] if numbers else None}

