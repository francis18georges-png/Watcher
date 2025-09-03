# Sandbox: point d'entrée pour exécutions confinées avec quotas

from typing import TypedDict

class RunResult(TypedDict):
    code: int | None
    out: str
    err: str
    timeout: bool
    cpu_exceeded: bool
    memory_exceeded: bool


def run(
    cmd: list[str],
    *,
    cpu_seconds: int | None = None,
    memory_bytes: int | None = None,
    timeout: float | None = 30,
) -> RunResult:
    """Exécute ``cmd`` avec quotas optionnels.

    Args:
        cmd: Commande à lancer.
        cpu_seconds: Limite de temps CPU en secondes.
        memory_bytes: Limite mémoire maximale en octets.
        timeout: Temps d'expiration mur (timeout) pour ``subprocess.run``.

    Returns:
        dict: Informations d'exécution comprenant codes et dépassements.
    """

    import resource
    import signal
    import subprocess

    def _limits() -> None:
        if cpu_seconds is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if memory_bytes is not None:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    result: RunResult = {
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
        result.update({"code": p.returncode, "out": p.stdout, "err": p.stderr})
        if p.returncode and p.returncode < 0:
            sig = -p.returncode
            if sig == signal.SIGXCPU:
                result["cpu_exceeded"] = True
            elif sig == signal.SIGKILL:
                result["memory_exceeded"] = True
    except subprocess.TimeoutExpired as e:
        result.update(
            {
                "timeout": True,
                "out": str(e.stdout or ""),
                "err": str(e.stderr or ""),
            }
        )
    return result
