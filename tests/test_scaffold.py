import pytest
from pathlib import Path

from app.tools.scaffold import create_python_cli


@pytest.mark.parametrize("name", ["foo", "Bar", "baz_123", "_underscore"])
def test_create_python_cli_accepts_valid_names(tmp_path, name):
    proj_dir = Path(create_python_cli(name, tmp_path))
    assert proj_dir.name == name
    assert proj_dir.exists()


@pytest.mark.parametrize("name", ["123abc", "bad-name", "bad name", "name!", ""])
def test_create_python_cli_rejects_invalid_names(tmp_path, name):
    with pytest.raises(ValueError):
        create_python_cli(name, tmp_path)
