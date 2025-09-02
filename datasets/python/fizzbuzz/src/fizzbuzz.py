"""FizzBuzz exercise utility."""


def fizzbuzz(n: int) -> str:
    """Return fizz/buzz/fizzbuzz or the number itself.

    Examples
    --------
    >>> fizzbuzz(3)
    'fizz'
    >>> fizzbuzz(5)
    'buzz'
    >>> fizzbuzz(15)
    'fizzbuzz'
    """
    if n % 3 == 0 and n % 5 == 0:
        return "fizzbuzz"
    if n % 3 == 0:
        return "fizz"
    if n % 5 == 0:
        return "buzz"
    return str(n)
