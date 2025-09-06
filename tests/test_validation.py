import pytest

from app.core.validation import validate_prompt
from app.data.validation import validate_dataset


def test_validate_prompt_valid() -> None:
    assert validate_prompt("Hello") == "Hello"


def test_validate_prompt_empty() -> None:
    with pytest.raises(ValueError):
        validate_prompt("")


def test_validate_prompt_type() -> None:
    with pytest.raises(TypeError):
        validate_prompt(123)


# ---------------------------------------------------------------------------
# Dataset validation tests
# ---------------------------------------------------------------------------

def _make_dataset(
    tmp_path,
    *,
    include_src: bool = True,
    include_tests: bool = True,
    include_meta: bool = True,
):
    ds = tmp_path / "task"
    ds.mkdir()
    if include_src:
        (ds / "src").mkdir()
    if include_tests:
        (ds / "tests").mkdir()
    if include_meta:
        (ds / "meta.json").write_text("{}", encoding="utf-8")
    return ds


def test_validate_dataset_missing_path(tmp_path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        validate_dataset(missing)


def test_validate_dataset_not_directory(tmp_path) -> None:
    file_path = tmp_path / "file"
    file_path.write_text("hi", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        validate_dataset(file_path)


def test_validate_dataset_missing_src(tmp_path) -> None:
    ds = _make_dataset(tmp_path, include_src=False)
    with pytest.raises(FileNotFoundError) as exc:
        validate_dataset(ds)
    assert str(ds / "src") in str(exc.value)


def test_validate_dataset_missing_tests(tmp_path) -> None:
    ds = _make_dataset(tmp_path, include_tests=False)
    with pytest.raises(FileNotFoundError) as exc:
        validate_dataset(ds)
    assert str(ds / "tests") in str(exc.value)


def test_validate_dataset_missing_meta(tmp_path) -> None:
    ds = _make_dataset(tmp_path, include_meta=False)
    with pytest.raises(FileNotFoundError) as exc:
        validate_dataset(ds)
    assert str(ds / "meta.json") in str(exc.value)
