import subprocess
import sys
import pathlib


def test_exit_stack_closed(tmp_path):
    marker = tmp_path / "marker.txt"
    root = pathlib.Path(__file__).resolve().parents[1]
    script = tmp_path / "script.py"
    script.write_text(
        f"""
import sys, pathlib
sys.path.insert(0, {str(root)!r})
from app.core import autograder

class DummyCtx:
    def __init__(self, path):
        self.path = pathlib.Path(path)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.path.write_text("closed")

autograder._STACK.enter_context(DummyCtx({str(marker)!r}))
"""
    )
    subprocess.run([sys.executable, str(script)], check=True)
    assert marker.read_text() == "closed"
