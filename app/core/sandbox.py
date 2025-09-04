# Sandbox: point d'entrée pour exécutions confinées avec quotas


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
        msg = (
            "Resource limits are not implemented on Windows. "
            "Use subprocess.CREATE_JOB_OBJECT to enforce limits."
        )
        raise NotImplementedError(msg)
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
