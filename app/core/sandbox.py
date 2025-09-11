# Sandbox: point d'entrée pour exécutions confinées avec quotas

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Résultat d'une exécution sandboxée."""

    code: int | None = None
    out: str = ""
    err: str = ""
    timeout: bool = False
    cpu_exceeded: bool = False
    memory_exceeded: bool = False


def _run_without_pywin32(
    cmd: list[str], timeout: float | None
) -> SandboxResult:
    """Fallback execution for Windows when pywin32 is unavailable."""
    import subprocess
    from subprocess import CompletedProcess

    result = SandboxResult()
    try:
        cp: CompletedProcess[str] = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = cp.stdout if isinstance(cp.stdout, str) else ""
        err = cp.stderr if isinstance(cp.stderr, str) else ""
        result.code = cp.returncode
        result.out = out
        result.err = err
    except subprocess.TimeoutExpired as e:
        result.timeout = True
        result.out = e.stdout if isinstance(e.stdout, str) else ""
        result.err = e.stderr if isinstance(e.stderr, str) else ""

    return result


def run(
    cmd: list[str],
    *,
    cpu_seconds: int | None = None,
    memory_bytes: int | None = None,
    timeout: float | None = 30,
) -> SandboxResult:
    """Exécute ``cmd`` avec quotas optionnels.

    Args:
        cmd: Commande à lancer.
        cpu_seconds: Limite de temps CPU en secondes.
        memory_bytes: Limite mémoire maximale en octets.
        timeout: Temps d'expiration mur (timeout) pour ``subprocess.run``.

    Returns:
        SandboxResult: Informations d'exécution comprenant codes et dépassements.
    """
    import sys

    result = SandboxResult()

    if sys.platform == "win32":
        import subprocess
        from subprocess import Popen
        from typing import Any, Callable, cast

        try:
            import win32con
            import win32job
            from win32api import CloseHandle, OpenProcess
        except ImportError:
            logger.warning(
                "pywin32 introuvable; exécution sans quotas CPU/mémoire sur Windows"
            )
            return _run_without_pywin32(cmd, timeout)

        CloseHandle = cast(Callable[[int], None], CloseHandle)

        job = cast(Any, win32job.CreateJobObject(None, ""))  # type: ignore[attr-defined, func-returns-value]
        info = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation  # type: ignore[attr-defined]
        )
        flags = info["BasicLimitInformation"]["LimitFlags"]
        if cpu_seconds is not None:
            info["BasicLimitInformation"]["PerProcessUserTimeLimit"] = int(
                cpu_seconds * 10_000_000
            )
            flags |= win32job.JOB_OBJECT_LIMIT_PROCESS_TIME
        if memory_bytes is not None:
            info["ProcessMemoryLimit"] = int(memory_bytes)
            flags |= win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info["BasicLimitInformation"]["LimitFlags"] = flags
        win32job.SetInformationJobObject(
            job,
            win32job.JobObjectExtendedLimitInformation,  # type: ignore[attr-defined]
            info,
        )

        creation_flags = subprocess.CREATE_NEW_CONSOLE
        p: Popen[str] = Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
        )
        handle = OpenProcess(win32con.PROCESS_ALL_ACCESS, False, p.pid)
        win32job.AssignProcessToJobObject(job, handle)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            result.timeout = True
        result.code = p.returncode
        result.out = out if isinstance(out, str) else ""
        result.err = err if isinstance(err, str) else ""
        try:
            violation = win32job.QueryInformationJobObject(
                job, win32job.JobObjectLimitViolationInformation  # type: ignore[attr-defined]
            )
            vflags = violation.get("LimitFlags", 0) | violation.get(
                "ViolationLimitFlags", 0
            )
            if vflags & win32job.JOB_OBJECT_LIMIT_PROCESS_TIME:
                result.cpu_exceeded = True
            if vflags & win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY:
                result.memory_exceeded = True
        except OSError as exc:
            logger.debug("Could not query job object: %s", exc)
        except Exception:
            logger.exception("Unexpected error querying job object")
        finally:
            try:
                CloseHandle(handle)  # type: ignore[attr-defined]
            except OSError as exc:
                logger.debug("Failed to close process handle: %s", exc)
            except Exception:
                logger.exception("Unexpected error closing process handle")
            try:
                CloseHandle(job)
            except OSError as exc:
                logger.debug("Failed to close job handle: %s", exc)
            except Exception:
                logger.exception("Unexpected error closing job handle")
        return result
    import resource
    import signal
    import subprocess

    def _limits() -> None:
        if cpu_seconds is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if memory_bytes is not None:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    from subprocess import Popen
    from typing import cast

    p: Popen[str] = Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_limits if cpu_seconds or memory_bytes else None,
    )

    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        result.timeout = True

    out_str = cast(str, out) if isinstance(out, str) else ""
    err_str = cast(str, err) if isinstance(err, str) else ""
    result.code = p.returncode
    result.out = out_str
    result.err = err_str
    if p.returncode and p.returncode < 0:
        sig = -p.returncode
        if sig == signal.SIGXCPU:
            result.cpu_exceeded = True
        elif sig == signal.SIGKILL:
            result.memory_exceeded = True
    return result
