import sys
import logging

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


def test_run_windows_without_pywin32(monkeypatch, caplog):
    """Simule Windows sans pywin32 et vérifie l'avertissement."""
    import builtins
    import subprocess

    monkeypatch.setattr(sys, "platform", "win32")

    real_import = builtins.__import__

    def _mock_import(name, *args, **kwargs):
        if name in {"win32con", "win32job", "win32api"}:
            raise ImportError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _mock_import)

    called = {"popen": False}

    def _fake_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be used")

    class _FakeProc:
        pid = 123
        returncode = 0

        def communicate(self, timeout=None):
            return ("hi\n", "")

        def kill(self):  # pragma: no cover - stub
            pass

    def _fake_popen(*args, **kwargs):
        called["popen"] = True
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    with caplog.at_level(logging.WARNING):
        result = sandbox.run(["python", "-c", "print('hi')"])

    assert called["popen"] is True
    assert isinstance(result, sandbox.SandboxResult)
    assert result.code == 0
    assert result.out.strip() == "hi"
    assert result.err == ""
    assert result.timeout is False
    assert result.cpu_exceeded is False
    assert result.memory_exceeded is False
    assert "pywin32 introuvable" in caplog.text


def test_run_windows_with_pywin32(monkeypatch, caplog):
    """Simule Windows avec pywin32 pour vérifier la voie normale."""
    import types

    monkeypatch.setattr(sys, "platform", "win32")

    import subprocess

    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 0, raising=False)

    win32con = types.ModuleType("win32con")
    win32con.PROCESS_ALL_ACCESS = 0x1

    win32api = types.ModuleType("win32api")

    def _close_handle(handle: int) -> None:  # pragma: no cover - stub
        return None

    def _open_process(
        flags: int, inherit: bool, pid: int
    ) -> int:  # pragma: no cover - stub
        return 1

    win32api.CloseHandle = _close_handle
    win32api.OpenProcess = _open_process

    win32job = types.ModuleType("win32job")

    def _create_job_object(arg1, arg2):  # pragma: no cover - stub
        return 1

    def _query_information_job_object(job, info_class):  # pragma: no cover - stub
        if info_class == win32job.JobObjectExtendedLimitInformation:
            return {"BasicLimitInformation": {"LimitFlags": 0}}
        if info_class == win32job.JobObjectLimitViolationInformation:
            return {"LimitFlags": 0, "ViolationLimitFlags": 0}
        return {}

    def _set_information_job_object(job, info_class, info):  # pragma: no cover - stub
        return None

    def _assign_process_to_job_object(job, handle):  # pragma: no cover - stub
        return None

    win32job.CreateJobObject = _create_job_object
    win32job.QueryInformationJobObject = _query_information_job_object
    win32job.SetInformationJobObject = _set_information_job_object
    win32job.AssignProcessToJobObject = _assign_process_to_job_object
    win32job.JobObjectExtendedLimitInformation = 1
    win32job.JobObjectLimitViolationInformation = 2
    win32job.JOB_OBJECT_LIMIT_PROCESS_TIME = 0x1
    win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x2

    monkeypatch.setitem(sys.modules, "win32con", win32con)
    monkeypatch.setitem(sys.modules, "win32api", win32api)
    monkeypatch.setitem(sys.modules, "win32job", win32job)

    with caplog.at_level(logging.WARNING):
        result = sandbox.run(["python", "-c", "print('hi')"])

    assert "pywin32 introuvable" not in caplog.text
    assert isinstance(result, sandbox.SandboxResult)
    assert result.code == 0
    assert result.out.strip() == "hi"
    assert result.err == ""
    assert result.timeout is False
    assert result.cpu_exceeded is False
    assert result.memory_exceeded is False
