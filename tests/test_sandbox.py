import sys

import pytest

from app.core import sandbox


# Skip Unix test when running on any Windows platform
@pytest.mark.skipif(sys.platform.startswith("win"), reason="non-Windows only")
def test_run_unix_executes_command():
    result = sandbox.run(["python", "-c", "print('hi')"])
    assert result.code == 0
    assert result.out.strip() == "hi"
    assert result.timeout is False
    assert result.cpu_exceeded is False
    assert result.memory_exceeded is False


# Skip Windows test when not running on Windows
@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_run_windows_executes_command():
    result = sandbox.run(["python", "-c", "print('hi')"])
    assert result.code == 0
    assert result.out.strip() == "hi"
    assert result.timeout is False
    assert result.cpu_exceeded is False
    assert result.memory_exceeded is False
