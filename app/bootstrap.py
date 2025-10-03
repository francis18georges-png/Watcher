"""Startup helpers that ensure the user environment is initialised."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.first_run import FirstRunConfigurator


def auto_configure_if_needed(home: Path | None = None) -> None:
    """Run the first-run configurator when the sentinel is present."""

    configurator = FirstRunConfigurator(home=home)
    if not configurator.sentinel_path.exists():
        return

    skip_models = os.environ.get("WATCHER_BOOTSTRAP_SKIP_MODELS") == "1"
    configurator.run(auto=True, download_models=not skip_models)


__all__ = ["auto_configure_if_needed"]

