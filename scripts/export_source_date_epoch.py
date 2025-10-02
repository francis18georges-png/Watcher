#!/usr/bin/env python3
"""Compute SOURCE_DATE_EPOCH and export it for GitHub Actions."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from typing import Iterable, Mapping, Optional


def _candidate_refs(env: Mapping[str, str]) -> Iterable[str]:
    ref = env.get("GITHUB_REF")
    if ref:
        yield ref

    ref_name = env.get("GITHUB_REF_NAME")
    if ref_name:
        yield f"refs/tags/{ref_name}"

    yield "HEAD"


def _resolve_epoch(refs: Iterable[str]) -> Optional[str]:
    for candidate in refs:
        try:
            value = subprocess.check_output(
                ["git", "log", "-1", "--format=%ct", candidate],
                text=True,
            ).strip()
        except subprocess.CalledProcessError:
            continue
        if value:
            return value
    return None


def main() -> int:
    env = os.environ

    workspace_raw = env.get("GITHUB_WORKSPACE")
    if not workspace_raw:
        raise SystemExit("GITHUB_WORKSPACE environment variable is not set")

    workspace = pathlib.Path(workspace_raw)
    (workspace / ".pyinstaller").mkdir(parents=True, exist_ok=True)

    epoch = _resolve_epoch(_candidate_refs(env))
    if epoch is None:
        raise SystemExit("Unable to determine SOURCE_DATE_EPOCH")

    github_env_path = env.get("GITHUB_ENV")
    if not github_env_path:
        raise SystemExit("GITHUB_ENV environment variable is not set")

    github_env = pathlib.Path(github_env_path)
    with github_env.open("a", encoding="utf-8") as fh:
        fh.write(f"SOURCE_DATE_EPOCH={epoch}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
