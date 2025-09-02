import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from is_prime import is_prime


def test_small():
    assert is_prime(2)
    assert is_prime(3)
    assert not is_prime(1)
    assert not is_prime(4)


def test_more():
    assert is_prime(13)
    assert not is_prime(121)
