import pathlib
import runpy

fizzbuzz = runpy.run_path(
    str(pathlib.Path(__file__).resolve().parents[1] / "src" / "fizzbuzz.py")
)["fizzbuzz"]


def test_samples():
    assert fizzbuzz(1) == "1"
    assert fizzbuzz(3) == "fizz"
    assert fizzbuzz(5) == "buzz"
    assert fizzbuzz(15) == "fizzbuzz"
