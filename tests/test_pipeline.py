import pytest

from app.core.pipeline import (
    apply_hooks,
    load_raw_data,
    normalize_and_dedup,
    stream_raw_data,
    transform_data,
)


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


def test_normalize_and_hooks():
    lines = [" A ", "b", "a"]
    normed = normalize_and_dedup(lines)
    assert normed == ["a", "b"]

    def hook(data: list[str]) -> list[str]:
        return [d + "!" for d in data]

    out = apply_hooks(normed, [hook])
    assert out == ["a!", "b!"]


def test_apply_hooks_tolerates_errors():
    def bad(data: list[str]) -> list[str]:
        raise RuntimeError("boom")

    assert apply_hooks(["x"], [bad]) == ["x"]


def test_stream_raw_data(tmp_path):
    file = tmp_path / "numbers.txt"
    file.write_text("1\n2\n3\n4", encoding="utf-8")
    batches = list(stream_raw_data(file, batch_size=2))
    assert batches == [["1", "2"], ["3", "4"]]
