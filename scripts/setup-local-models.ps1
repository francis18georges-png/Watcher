Param(
    [string]$WatcherHome
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir/.."

if (-not $WatcherHome) {
    if ($env:WATCHER_HOME) {
        $WatcherHome = $env:WATCHER_HOME
    } else {
        $WatcherHome = Join-Path $env:USERPROFILE '.watcher'
    }
}

$env:WATCHER_HOME = $WatcherHome
$env:PYTHONPATH = "$ProjectRoot" + [System.IO.Path]::PathSeparator + ($env:PYTHONPATH)

python - <<'PY'
from pathlib import Path
import os

from app.core.model_registry import MODEL_REGISTRY, download_model

home = Path(os.environ.get("WATCHER_HOME", Path.home()))
base = home / "models"

targets = {
    "llama.cpp": base / "llm",
    "sentence-transformers": base / "embeddings",
}

base.mkdir(parents=True, exist_ok=True)

for specs in MODEL_REGISTRY.values():
    for spec in specs:
        target_dir = targets.get(spec.backend, base)
        path = download_model(spec, target_dir)
        print(f"✔ {spec.name} -> {path}")
PY
