"""Tests for the first-run configurator helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import cli
from app.bootstrap import auto_configure_if_needed
from app.core.first_run import FirstRunConfigurator
from config import get_settings


def _override_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    # When running under CI the ``HOME`` variable is honoured by
    # :func:`Path.home` on POSIX platforms.  ``USERPROFILE`` is the equivalent
    # for Windows runners.
    monkeypatch.setenv("USERPROFILE", str(home))


def test_first_run_creates_expected_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    configurator = FirstRunConfigurator(home=home)

    sentinel = configurator.sentinel_path
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("pending", encoding="utf-8")

    config_path = configurator.run(auto=True, download_models=False)

    assert config_path == home / ".watcher" / "config.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "[llm]" in content
    assert "model_path" in content

    policy_path = home / ".watcher" / "policy.yaml"
    assert policy_path.exists()
    content = policy_path.read_text(encoding="utf-8")
    assert "version: 1" in content

    ledger_path = home / ".watcher" / "consents.jsonl"
    assert ledger_path.exists()
    ledger_content = ledger_path.read_text(encoding="utf-8")
    assert '"type": "metadata"' in ledger_content
    assert '"action": "init"' in ledger_content

    env_path = home / ".watcher" / ".env"
    assert env_path.exists()
    env_content = env_path.read_text(encoding="utf-8")
    assert "WATCHER_LLM__MODEL_SHA256" in env_content
    assert "WATCHER_POLICY__SHA256" in env_content

    assert not sentinel.exists()


def test_user_config_overrides_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".watcher").mkdir(parents=True)
    (home / ".watcher" / "config.toml").write_text(
        """
        [llm]
        ctx = 1024
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    _override_home(monkeypatch, home)

    # ``get_settings`` caches results.  Ensure we start from a clean slate.
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        settings = get_settings()
        assert settings.llm.ctx == 1024
    finally:
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_bootstrap_auto_configures_when_sentinel_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    configurator = FirstRunConfigurator(home=home)
    configurator.config_dir.mkdir(parents=True, exist_ok=True)
    configurator.sentinel_path.write_text("pending", encoding="utf-8")

    monkeypatch.setenv("WATCHER_BOOTSTRAP_SKIP_MODELS", "1")

    auto_configure_if_needed(home=home)

    assert configurator.config_path.exists()
    assert not configurator.sentinel_path.exists()


def test_bootstrap_creates_config_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"

    monkeypatch.setenv("WATCHER_BOOTSTRAP_SKIP_MODELS", "1")

    auto_configure_if_needed(home=home)

    configurator = FirstRunConfigurator(home=home)
    assert configurator.config_path.exists()
    assert configurator.policy_path.exists()
    assert not configurator.sentinel_path.exists()


def test_cli_startup_bootstraps_clean_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("WATCHER_BOOTSTRAP_SKIP_MODELS", "1")

    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        exit_code = cli.main(["policy", "show"])
    finally:
        get_settings.cache_clear()  # type: ignore[attr-defined]

    assert exit_code == 0

    configurator = FirstRunConfigurator(home=home)
    assert configurator.config_path.exists()
    assert configurator.policy_path.exists()
    assert not configurator.sentinel_path.exists()
