FROM mcr.microsoft.com/devcontainers/python:3.12

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CACHE_DIR=/home/vscode/.cache/pip \
    DVC_CACHE_DIR=/workspaces/.cache/dvc \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0

RUN sudo apt-get update \
    && sudo apt-get install -y --no-install-recommends \
        git-lfs \
    && sudo rm -rf /var/lib/apt/lists/* \
    && git lfs install --system
