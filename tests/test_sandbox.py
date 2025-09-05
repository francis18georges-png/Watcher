import sys

import pytest

from app.core import sandbox

@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
def test_run_unix_executes_command():
    result = sandbox.run(["python", "-c", "print('hi')"])
    assert result["code"] == 0
    assert result["out"].strip() == "hi"
    assert result["timeout"] is False
    assert result["cpu_exceeded"] is False
    assert result["memory_exceeded"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_run_windows_executes_command():
    result = sandbox.run(["python", "-c", "print('hi')"])
    assert result["code"] == 0
    assert result["out"].strip() == "hi"
    assert result["timeout"] is False
    assert result["cpu_exceeded"] is False
    assert result["memory_exceeded"] is False
