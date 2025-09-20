# Sandbox: point d'entrée pour exécutions confinées avec quotas

import logging
import os
from dataclasses import dataclass
from typing import Mapping

logger = logging.getLogger(__name__)

_ALLOWED_ENV_VARS = {
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "SYSTEMROOT",
    "COMSPEC",
    "WINDIR",
    "HOME",
    "USERPROFILE",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
}


@dataclass
class SandboxResult:
    """Résultat d'une exécution sandboxée."""

    code: int | None = None
    out: str = ""
    err: str = ""
    timeout: bool = False
    cpu_exceeded: bool = False
    memory_exceeded: bool = False


def _prepare_environment(extra: Mapping[str, str | None] | None = None) -> dict[str, str]:
    """Return a sanitized environment dictionary.

    ``extra`` values set to ``None`` explicitly remove a key from the final
    environment which allows callers to opt-out from inherited variables.
    """

    env: dict[str, str] = {}
    for key in _ALLOWED_ENV_VARS:
        value = os.environ.get(key)
        if value:
            env[key] = value

    path = os.environ.get("PATH")
    if path:
        env.setdefault("PATH", path)

    if extra:
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value

    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _install_seccomp_network_filter() -> None:
    """Best effort network filter using seccomp when available."""

    try:
        import errno
        import seccomp
    except Exception:
        # ``seccomp`` might be unavailable on certain systems.  In this case we
        # still rely on environment based network blocking inside the executed
        # Python process.
        return

    filt = seccomp.SyscallFilter(defaction=seccomp.SCMP_ACT_ALLOW)
    for syscall in [
        "socket",
        "connect",
        "accept",
        "accept4",
        "sendto",
        "sendmsg",
        "recvfrom",
        "recvmsg",
        "getsockname",
        "getpeername",
        "bind",
        "listen",
    ]:
        try:
            filt.add_rule(seccomp.SCMP_ACT_ERRNO(errno.EPERM), syscall)
        except OSError:
            continue
    try:
        filt.load()
    except OSError:
        # Loading the filter can fail on platforms where seccomp is not
        # permitted.  The execution still proceeds albeit without kernel level
        # filtering, falling back to the Python level guard.
        logger.debug("Unable to install seccomp filter", exc_info=True)


def _run_without_pywin32(
    cmd: list[str],
    timeout: float | None,
    cwd: str | os.PathLike[str] | None,
    env: Mapping[str, str],
) -> SandboxResult:
    """Fallback execution for Windows when pywin32 is unavailable."""
    import subprocess
    from subprocess import Popen

    p: Popen[str] = Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=dict(env),
    )

    try:
        out, err = p.communicate(timeout=timeout)
        timeout_flag = False
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        timeout_flag = True

    out_str = out if isinstance(out, str) else ""
    err_str = err if isinstance(err, str) else ""
    return SandboxResult(
        code=p.returncode,
        out=out_str,
        err=err_str,
        timeout=timeout_flag,
    )


def run(
    cmd: list[str],
    *,
    cpu_seconds: int | None = None,
    memory_bytes: int | None = None,
    timeout: float | None = 30,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str | None] | None = None,
    allow_network: bool = False,
) -> SandboxResult:
    """Exécute ``cmd`` avec quotas optionnels.

    Args:
        cmd: Commande à lancer.
        cpu_seconds: Limite de temps CPU en secondes.
        memory_bytes: Limite mémoire maximale en octets.
        timeout: Temps d'expiration mur (timeout) pour ``subprocess.run``.
        cwd: Répertoire de travail isolé pour le processus enfant.
        env: Variables d'environnement additionnelles à injecter après
            nettoyage. Les valeurs explicites ``None`` retirent les clés
            correspondantes de l'environnement final.
        allow_network: Autoriser (``True``) ou bloquer (``False``) l'accès
            réseau.

    Returns:
        SandboxResult: Informations d'exécution comprenant codes et dépassements.
    """
    import sys

    result = SandboxResult()

    sanitized_env = _prepare_environment(env)
    if not allow_network:
        sanitized_env["WATCHER_BLOCK_NETWORK"] = "1"

    cwd_path = os.fspath(cwd) if cwd is not None else None

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
            return _run_without_pywin32(cmd, timeout, cwd_path, sanitized_env)

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
        win_proc: Popen[str] = Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
            cwd=cwd_path,
            env=sanitized_env,
        )
        handle = OpenProcess(win32con.PROCESS_ALL_ACCESS, False, win_proc.pid)
        win32job.AssignProcessToJobObject(job, handle)
        try:
            out, err = win_proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            win_proc.kill()
            out, err = win_proc.communicate()
            result.timeout = True
        result.code = win_proc.returncode
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

    def _preexec() -> None:
        if cpu_seconds is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if memory_bytes is not None:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        if not allow_network:
            _install_seccomp_network_filter()

    from subprocess import Popen
    from typing import cast

    preexec = _preexec if (cpu_seconds or memory_bytes or not allow_network) else None

    proc: Popen[str] = Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=preexec,
        cwd=cwd_path,
        env=sanitized_env,
        close_fds=True,
    )

    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        result.timeout = True

    out_str = cast(str, out) if isinstance(out, str) else ""
    err_str = cast(str, err) if isinstance(err, str) else ""
    result.code = proc.returncode
    result.out = out_str
    result.err = err_str
    if proc.returncode and proc.returncode < 0:
        sig = -proc.returncode
        if sig == signal.SIGXCPU:
            result.cpu_exceeded = True
        elif sig == signal.SIGKILL:
            result.memory_exceeded = True
    return result
