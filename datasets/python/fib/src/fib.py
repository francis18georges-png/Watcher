"""Fibonacci sequence utilities."""


def fib(n: int) -> int:
    """Return the n-th Fibonacci number.

    Examples
    --------
    >>> fib(5)
    5
    >>> fib(7)
    13
    """
    if n < 0:
        raise ValueError("n>=0")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
