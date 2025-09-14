import json
import time
import pytest
from app.core.memory import Memory
from app.data.pipeline import (
    RAW_DIR,
    load_raw_data,
    normalize_data,
    transform_data as save_data,
)
from app.core.pipeline import transform_data

RAW_DIR.mkdir(parents=True, exist_ok=True)


def test_normalize_data_dedup_and_outliers():
    data = {"nums": [1, 2, 2, 1000], "text": "  hi  ", "dup": ["a", "a", "b"]}
    result = normalize_data(data)
    assert result["text"] == "hi"
    assert result["dup"] == ["a", "b"]
    assert result["nums"] == [1, 2]


def test_normalize_data_dedup_with_dicts():
    data = {"items": [{"a": 1}, {"a": 1}, {"b": 2}]}
    result = normalize_data(data)
    assert result["items"] == [{"a": 1}, {"b": 2}]


def test_load_raw_data_missing_file(caplog):
    missing = RAW_DIR / "missing.json"
    if missing.exists():
        missing.unlink()
    with caplog.at_level("ERROR", logger="app.data.pipeline"):
        with pytest.raises(FileNotFoundError):
            load_raw_data(missing)
    assert "does not exist" in caplog.text
    assert all(record.name == "app.data.pipeline" for record in caplog.records)


def test_load_raw_data_invalid_format(caplog):
    bad = RAW_DIR / "bad.txt"
    bad.write_text("{}", encoding="utf-8")
    with caplog.at_level("ERROR", logger="app.data.pipeline"):
        with pytest.raises(ValueError):
            load_raw_data(bad)
    assert "unsupported format" in caplog.text
    assert all(record.name == "app.data.pipeline" for record in caplog.records)
    bad.unlink()


def test_load_raw_data_invalid_json(caplog):
    bad = RAW_DIR / "bad.json"
    bad.write_text("{bad}", encoding="utf-8")
    with caplog.at_level("ERROR", logger="app.data.pipeline"):
        with pytest.raises(json.JSONDecodeError):
            load_raw_data(bad)
    assert "invalid JSON" in caplog.text
    assert all(record.name == "app.data.pipeline" for record in caplog.records)
    bad.unlink()


def test_load_raw_data_path_escape(caplog):
    with caplog.at_level("ERROR", logger="app.data.pipeline"):
        with pytest.raises(ValueError):
            load_raw_data("../evil.json")
    assert "escapes RAW_DIR" in caplog.text
    assert all(record.name == "app.data.pipeline" for record in caplog.records)


def test_transform_data_path_traversal():
    with pytest.raises(ValueError):
        save_data({}, filename="../evil.json")


def test_raw_batch_loading_benchmark():
    """Compare individual file loading with directory batch loading."""

    tmp_dir = RAW_DIR / "tmp_batch"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(50):
        f = tmp_dir / f"data_{i}.json"
        f.write_text("{}", encoding="utf-8")
        files.append(f)

    start = time.perf_counter()
    for f in files:
        load_raw_data(f)
    sequential = time.perf_counter() - start

    start = time.perf_counter()
    load_raw_data(tmp_dir)
    batched = time.perf_counter() - start

    for f in files:
        f.unlink()
    tmp_dir.rmdir()

    assert batched <= sequential


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

    assert batched <= baseline * 1.1


def test_transform_data_invalid_line(caplog):
    lines = ["1", "foo", "2"]
    with caplog.at_level("WARNING"):
        result = transform_data(lines)
    assert result == [1, 2]
    assert "invalid integer" in caplog.text
