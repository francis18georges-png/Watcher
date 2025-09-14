import json
import time
import pytest
from app.core.memory import Memory
from app.data.pipeline import load_raw_data, normalize_data


def test_normalize_data_dedup_and_outliers():
    data = {"nums": [1, 2, 2, 1000], "text": "  hi  ", "dup": ["a", "a", "b"]}
    result = normalize_data(data)
    assert result["text"] == "hi"
    assert result["dup"] == ["a", "b"]
    assert result["nums"] == [1, 2]


def test_load_raw_data_missing_file(tmp_path, caplog):
    missing = tmp_path / "data.json"
    with pytest.raises(FileNotFoundError):
        load_raw_data(missing)
    assert "does not exist" in caplog.text


def test_load_raw_data_invalid_format(tmp_path, caplog):
    bad = tmp_path / "data.txt"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_raw_data(bad)
    assert "unsupported format" in caplog.text


def test_load_raw_data_invalid_json(tmp_path, caplog):
    bad = tmp_path / "data.json"
    bad.write_text("{bad}", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_raw_data(bad)
    assert "invalid JSON" in caplog.text


def test_feedback_batch_loading_benchmark(tmp_path):
    """Compare naive feedback loading with batched iteration."""

    mem = Memory(tmp_path / "mem.db")
    for i in range(1000):
        mem.add_feedback("k", f"p{i}", f"a{i}", float(i))

    start = time.perf_counter()
    mem.all_feedback()
    baseline = time.perf_counter() - start

    start = time.perf_counter()
    list(mem.iter_feedback(batch_size=200))
    batched = time.perf_counter() - start

    assert batched <= baseline
