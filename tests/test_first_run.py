"""Tests for the first-run configurator helper."""

from __future__ import annotations

from pathlib import Path

import pytest

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

    recorded: dict[str, object] = {}

    def _fake_autostart(**kwargs):
        recorded.update(kwargs)
        return True

    monkeypatch.setattr("app.core.first_run.configure_autostart", _fake_autostart)

    config_path = configurator.run(fully_auto=True, download_models=False)

    assert config_path == home / ".watcher" / "config.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "[llm]" in content
    assert "model_path" in content

    policy_path = home / ".watcher" / "policy.yaml"
    assert policy_path.exists()
    content = policy_path.read_text(encoding="utf-8")
    assert "version: 1" in content

    ledger_path = home / ".watcher" / "consent-ledger.jsonl"
    assert ledger_path.exists()
    ledger_content = ledger_path.read_text(encoding="utf-8")
    assert '"type": "metadata"' in ledger_content

    assert recorded.get("home") == home
    assert recorded.get("consent_granted") is False


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
