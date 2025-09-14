import runpy  # ensure CLI module runs without NameError
import sys
from pathlib import Path
import logging

import pytest

from app.tools.scaffold import create_python_cli


def test_create_python_cli(tmp_path, caplog):
    proj_dir = Path(create_python_cli("foo", tmp_path))
    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = ["foo", "--ping"]
    try:
        caplog.set_level(logging.INFO)
        runpy.run_module("foo.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert "pong" in caplog.text


def test_create_python_cli_refuses_overwrite_without_force(tmp_path):
    proj_dir = tmp_path / "app" / "projects" / "foo"
    proj_dir.mkdir(parents=True)
    (proj_dir / "existing.txt").write_text("content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        create_python_cli("foo", tmp_path)


def test_create_python_cli_force_overwrite(tmp_path, caplog):
    proj_dir = tmp_path / "app" / "projects" / "foo"
    (proj_dir / "foo").mkdir(parents=True)
    (proj_dir / "foo/cli.py").write_text("print('old')\n", encoding="utf-8")

    proj_dir = Path(create_python_cli("foo", tmp_path, force=True))
    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = ["foo", "--ping"]
    try:
        caplog.set_level(logging.INFO)
        runpy.run_module("foo.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert "pong" in caplog.text
