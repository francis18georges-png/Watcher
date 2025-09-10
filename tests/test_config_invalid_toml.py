import logging
import tomllib
import pytest

from config import _read_toml


def test_invalid_toml_logs_and_raises(tmp_path, caplog):
    invalid = tmp_path / "bad.toml"
    invalid.write_text("invalid = [")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(tomllib.TOMLDecodeError):
            _read_toml(invalid)
    assert "Invalid TOML" in caplog.text
