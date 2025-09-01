import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from fib import fib

def test_values():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(10) == 55
