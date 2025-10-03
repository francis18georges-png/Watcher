#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

python - <<'PY'
from pathlib import Path
import os

from app.core.model_registry import MODEL_REGISTRY, download_model

home = Path(os.environ.get("WATCHER_HOME", Path.home()))
base = home / ".watcher" / "models"

targets = {
    "llama.cpp": base / "llm",
    "sentence-transformers": base / "embeddings",
}

base.mkdir(parents=True, exist_ok=True)

for family, specs in MODEL_REGISTRY.items():
    for spec in specs:
        target_dir = targets.get(spec.backend, base)
        path = download_model(spec, target_dir)
        print(f"✔ {spec.name} -> {path}")
PY
