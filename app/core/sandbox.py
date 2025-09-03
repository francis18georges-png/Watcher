# Sandbox: point d'entrée pour exécutions confinées (TODO quotas/temps)

def run(
    cmd: list[str], *, cwd: str | None = None, timeout: int = 30
) -> dict:
    import subprocess

    p = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
    )
    return {"code": p.returncode, "out": p.stdout, "err": p.stderr}

