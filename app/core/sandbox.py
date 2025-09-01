# Sandbox: point d'entrée pour exécutions confinées (TODO quotas/temps)
def run(cmd: list[str]) -> dict:
    import subprocess
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {'code':p.returncode,'out':p.stdout,'err':p.stderr}
