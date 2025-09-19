#!/usr/bin/env bash
set -euo pipefail

mkdir -p /home/vscode/.cache/pip
mkdir -p /workspaces/.cache/dvc

python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks for the default git user when available
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit install --install-hooks --overwrite
fi

# Warm DVC cache metadata if configuration exists
if command -v dvc >/dev/null 2>&1 && [ -d .dvc ]; then
  dvc config cache.shared group >/dev/null 2>&1 || true
fi
