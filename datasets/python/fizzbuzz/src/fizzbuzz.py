def fizzbuzz(n: int) -> str:
    """
    Retourne:
      "fizz" si multiple de 3
      "buzz" si multiple de 5
      "fizzbuzz" si multiple de 3 et 5
      sinon str(n)
    """
    # TODO: implémenter
    if n % 3 == 0 and n % 5 == 0:
        return "fizzbuzz"
    if n % 3 == 0:
        return "fizz"
    if n % 5 == 0:
        return "buzz"
    return str(n)
