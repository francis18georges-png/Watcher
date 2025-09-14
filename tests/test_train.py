import pytest

from train import train


def test_train_raises_value_error_on_empty_dataset():
    with pytest.raises(ValueError):
        train([], [])
