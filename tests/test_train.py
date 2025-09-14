import pytest
import train


def test_load_data_reads_dataset_correctly():
    xs, ys = train.load_data()
    assert xs == [float(x) for x in range(10)]
    assert ys == [2 * x + 1 for x in xs]


def test_train_returns_expected_parameters():
    xs, ys = train.load_data()
    w, b, mse = train.train(xs, ys)
    assert w == pytest.approx(2.0, abs=1e-2)
    assert b == pytest.approx(1.0, abs=1e-2)
    assert mse == pytest.approx(0.0, abs=1e-5)


def test_load_data_invalid_data_raises(monkeypatch, tmp_path):
    bad_file = tmp_path / "invalid.csv"
    bad_file.write_text("x,y\n1,not_a_number\n", encoding="utf-8")
    monkeypatch.setattr(train, "DATA_PATH", bad_file)
    with pytest.raises(ValueError):
        train.load_data()
