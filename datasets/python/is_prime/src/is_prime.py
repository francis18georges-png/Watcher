"""Primality test utilities."""

import math


def is_prime(n: int) -> bool:
    """Return ``True`` if ``n`` is prime for ``n >= 2``.

    Examples
    --------
    >>> is_prime(2)
    True
    >>> is_prime(4)
    False
    """
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    r = int(math.isqrt(n))
    f = 3
    while f <= r:
        if n % f == 0:
            return False
        f += 2
    return True
