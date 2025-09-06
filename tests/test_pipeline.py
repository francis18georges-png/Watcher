import pytest

from app.core.pipeline import load_raw_data, transform_data


def test_load_raw_data(tmp_path):
    file = tmp_path / "numbers.txt"
    file.write_text("1\n2\n\n3\n", encoding="utf-8")
    assert load_raw_data(file) == ["1", "2", "3"]


def test_load_raw_data_missing_file(tmp_path, caplog):
    missing = tmp_path / "absent.txt"
    with pytest.raises(FileNotFoundError):
        load_raw_data(missing)
    assert "does not exist" in caplog.text


def test_load_raw_data_invalid_format(tmp_path, caplog):
    bad = tmp_path / "numbers.json"
    bad.write_text("1\n2", encoding="utf-8")
    with pytest.raises(ValueError):
        load_raw_data(bad)
    assert "unsupported format" in caplog.text


def test_transform_data(tmp_path):
    file = tmp_path / "numbers.txt"
    file.write_text("1\n2\n3\n", encoding="utf-8")
    raw = load_raw_data(file)
    assert transform_data(raw) == [1, 2, 3]
