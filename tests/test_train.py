import pytest

from train import train


def test_train_learns_simple_linear_regression():
    xs = list(range(10))
    ys = [2 * x + 1 for x in xs]
    w, b, mse = train(xs, ys, lr=0.01, epochs=2000)
    assert w == pytest.approx(2, abs=0.01)
    assert b == pytest.approx(1, abs=0.01)
    assert mse == pytest.approx(0, abs=0.01)


def test_train_raises_value_error_on_empty_dataset():
    with pytest.raises(ValueError):
        train([], [])
