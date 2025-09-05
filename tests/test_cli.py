import runpy
import sys
from pathlib import Path

from app.tools.scaffold import create_python_cli


def test_create_python_cli(tmp_path, capsys):
    proj_dir = Path(create_python_cli("foo", tmp_path))
    sys.path.insert(0, str(proj_dir))
    argv = sys.argv
    sys.argv = ["foo", "--ping"]
    try:
        runpy.run_module("foo.cli", run_name="__main__")
    finally:
        sys.argv = argv
        sys.path.pop(0)
    assert capsys.readouterr().out.strip() == "pong"
