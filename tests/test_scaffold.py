import pytest
from pathlib import Path
import runpy
import sys
import logging

from app.tools.scaffold import create_python_cli, validate_name


@pytest.mark.parametrize("name", ["foo", "Bar", "baz_123", "_underscore"])
def test_validate_name_accepts_valid(name):
    assert validate_name(name) == name


@pytest.mark.parametrize("name", ["123abc", "bad-name", "bad name", "name!", ""])
def test_validate_name_rejects_invalid(name):
    with pytest.raises(ValueError):
        validate_name(name)


@pytest.mark.parametrize("name", ["foo", "Bar", "baz_123", "_underscore"])
def test_create_python_cli_accepts_valid_names(tmp_path, name, caplog):
    proj_dir = Path(create_python_cli(name, tmp_path))
    assert proj_dir.name == name
    assert proj_dir.exists()

    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = [name, "--ping"]
    try:
        caplog.set_level(logging.INFO)
        runpy.run_module(f"{name}.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert "pong" in caplog.text


@pytest.mark.parametrize("name", ["123abc", "bad-name", "bad name", "name!", ""])
def test_create_python_cli_rejects_invalid_names(tmp_path, name):
    with pytest.raises(ValueError):
        create_python_cli(name, tmp_path)
