# Sandbox: point d'entrée pour exécutions confinées avec quotas

import logging

logger = logging.getLogger(__name__)


def run(
    cmd: list[str],
    *,
    cpu_seconds: int | None = None,
    memory_bytes: int | None = None,
    timeout: float | None = 30,
) -> dict:
    """Exécute ``cmd`` avec quotas optionnels.

    Args:
        cmd: Commande à lancer.
        cpu_seconds: Limite de temps CPU en secondes.
        memory_bytes: Limite mémoire maximale en octets.
        timeout: Temps d'expiration mur (timeout) pour ``subprocess.run``.

    Returns:
        dict: Informations d'exécution comprenant codes et dépassements.
    """
    import sys

    if sys.platform == "win32":
        import subprocess
        import win32api  # type: ignore[import-not-found]
        import win32con  # type: ignore[import-not-found]
        import win32job  # type: ignore[import-not-found]

        result: dict[str, bool | int | str | None] = {
            "code": None,
            "out": "",
            "err": "",
            "timeout": False,
            "cpu_exceeded": False,
            "memory_exceeded": False,
        }

        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation
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
            job, win32job.JobObjectExtendedLimitInformation, info
        )

        creation_flags = subprocess.CREATE_NEW_CONSOLE
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
        )
        # Use an official Win32 API call to acquire a process handle from the
        # ``pid`` and assign it to the job object, avoiding reliance on private
        # ``subprocess.Popen`` attributes.
        handle = win32api.OpenProcess(
            win32con.PROCESS_SET_QUOTA
            | win32con.PROCESS_TERMINATE
            | win32con.PROCESS_QUERY_INFORMATION,
            False,
            p.pid,
        )
        try:
            win32job.AssignProcessToJobObject(job, handle)
        finally:
            win32api.CloseHandle(handle)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            result["timeout"] = True
        result["code"] = p.returncode
        result["out"] = out if isinstance(out, str) else ""
        result["err"] = err if isinstance(err, str) else ""
        try:
            violation = win32job.QueryInformationJobObject(
                job, win32job.JobObjectLimitViolationInformation
            )
            vflags = violation.get("LimitFlags", 0) | violation.get(
                "ViolationLimitFlags", 0
            )
            if vflags & win32job.JOB_OBJECT_LIMIT_PROCESS_TIME:
                result["cpu_exceeded"] = True
            if vflags & win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY:
                result["memory_exceeded"] = True
        except OSError as exc:
            logger.debug("Could not query job object: %s", exc)
        except Exception:
            logger.exception("Unexpected error querying job object")
        finally:
            try:
                win32job.CloseHandle(job)
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

    result: dict[str, bool | int | str | None] = {
        "code": None,
        "out": "",
        "err": "",
        "timeout": False,
        "cpu_exceeded": False,
        "memory_exceeded": False,
    }

    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_limits if cpu_seconds or memory_bytes else None,
        )
        from typing import cast

        out = cast(str, p.stdout) if isinstance(p.stdout, str) else ""
        err = cast(str, p.stderr) if isinstance(p.stderr, str) else ""
        result["code"] = p.returncode
        result["out"] = out
        result["err"] = err
        if p.returncode and p.returncode < 0:
            sig = -p.returncode
            if sig == signal.SIGXCPU:
                result["cpu_exceeded"] = True
            elif sig == signal.SIGKILL:
                result["memory_exceeded"] = True
    except subprocess.TimeoutExpired as e:
        result["timeout"] = True
        result["out"] = e.stdout if isinstance(e.stdout, str) else ""
        result["err"] = e.stderr if isinstance(e.stderr, str) else ""
    return result
