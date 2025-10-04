"""Startup helpers that ensure the user environment is initialised."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.first_run import FirstRunConfigurator


def auto_configure_if_needed(home: Path | None = None) -> None:
    """Ensure the user configuration exists before continuing."""

    configurator = FirstRunConfigurator(home=home)
    skip_models = os.environ.get("WATCHER_BOOTSTRAP_SKIP_MODELS") == "1"

    configurator.migrate_legacy_state()

    if not configurator.sentinel_path.exists():
        configurator.ensure_pending()

    if configurator.sentinel_path.exists():
        configurator.run(auto=True, download_models=not skip_models)
        return

    if configurator.is_configured():
        return

    configurator.run(auto=True, download_models=not skip_models)


__all__ = ["auto_configure_if_needed"]

