import pathlib
import runpy

fib = runpy.run_path(
    str(pathlib.Path(__file__).resolve().parents[1] / "src" / "fib.py")
)["fib"]


def test_values():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(10) == 55
