"""Utilities used to perform the first run auto-configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from secrets import token_bytes
from typing import Any

import json
import os
import platform
import shutil
import textwrap

from app.core.model_registry import ensure_models, select_models

@dataclass(slots=True)
class HardwareProfile:
    """Detected hardware capabilities relevant for local execution."""

    cpu_threads: int
    has_gpu: bool
    backend: str
    context_window: int


class FirstRunConfigurator:
    """Create a user configuration in ``~/.watcher`` on first launch."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or Path.home()
        self.config_dir = self.home / ".watcher"
        self.config_path = self.config_dir / "config.toml"
        self.policy_path = self.config_dir / "policy.yaml"
        self.consent_ledger = self.config_dir / "consent-ledger.jsonl"

    # ------------------------------------------------------------------
    # Hardware detection and recommendation helpers
    # ------------------------------------------------------------------
    def detect_hardware(self) -> HardwareProfile:
        """Return a :class:`HardwareProfile` describing the host machine."""

        cpu_threads = os.cpu_count() or 1
        has_gpu = shutil.which("nvidia-smi") is not None
        # llama.cpp stays the default backend for now – pick a larger context
        # window on beefier CPUs to keep prompts deterministic without user
        # interaction.
        if cpu_threads >= 16:
            context_window = 8192
        elif cpu_threads >= 8:
            context_window = 4096
        else:
            context_window = 2048

        backend = "llama.cpp"
        return HardwareProfile(
            cpu_threads=cpu_threads,
            has_gpu=has_gpu,
            backend=backend,
            context_window=context_window,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self, fully_auto: bool = False, download_models: bool = True
    ) -> Path:
        """Generate configuration files and return the created path.

        Parameters
        ----------
        fully_auto:
            When :data:`True`, no interactive prompt is displayed and sensible
            defaults are written immediately.  The non-interactive path is the
            only behaviour currently implemented which keeps the command
            scriptable for CI and automated deployments.
        download_models:
            When :data:`True`, all required model artifacts are downloaded or
            copied from embedded fallbacks before writing the configuration.
        """

        profile = self.detect_hardware()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        selection = select_models(profile.cpu_threads, profile.has_gpu)
        if download_models:
            self._download_models(selection)
        self._write_config(profile, selection)
        self._write_policy(selection)
        self._ensure_consent_ledger()
        return self.config_path

    # ------------------------------------------------------------------
    # File writers
    # ------------------------------------------------------------------
    def _download_models(self, selection: dict[str, Any]) -> None:
        models_dir = self.config_dir / "models"
        ensure_models(models_dir / "llm", [selection["llm"]])
        ensure_models(models_dir / "embeddings", [selection["embedding"]])

    def _write_config(
        self, profile: HardwareProfile, selection: dict[str, Any]
    ) -> None:
        data_dir = self.config_dir / "data"
        models_dir = self.config_dir / "models"
        llm_dir = models_dir / "llm"
        emb_dir = models_dir / "embeddings"

        config = {
            "paths": {
                "data_dir": str(data_dir),
                "memory_dir": str(self.config_dir / "memory"),
                "logs_dir": str(self.config_dir / "logs"),
                "models_dir": str(models_dir),
            },
            "llm": {
                "backend": profile.backend,
                "ctx": profile.context_window,
                "threads": profile.cpu_threads // 2 or 1,
                "model_path": str(llm_dir / selection["llm"].name),
                "model_sha256": selection["llm"].sha256,
                "model_license": selection["llm"].license,
            },
            "memory": {
                "db_path": str(self.config_dir / "memory" / "mem.db"),
                "embed_model_path": str(emb_dir / selection["embedding"].name),
                "embed_model_sha256": selection["embedding"].sha256,
            },
            "intelligence": {
                "mode": "offline",
            },
            "dev": {
                "logging": "info",
            },
            "security": {
                "sandbox_root": str(self.config_dir / "workspace"),
                "consent_ledger": str(self.consent_ledger),
            },
        }

        toml_text = self._toml_dump(config)
        self.config_path.write_text(toml_text, encoding="utf-8")

    def _write_policy(self, selection: dict[str, Any]) -> None:
        if self.policy_path.exists():
            return

        hostname = platform.node() or "localhost"
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        policy = textwrap.dedent(
            f"""
            version: 1
            subject:
              hostname: {hostname}
              generated_at: {now}
            defaults:
              offline: true
              require_consent: true
              kill_switch: false
            network:
              allowed_windows:
                - days: [mon, tue, wed, thu, fri]
                  window: "09:00-18:00"
              allowlist: []
              bandwidth_mb: 128
              time_budget_minutes: 15
            budgets:
              cpu_percent: 75
              ram_mb: 4096
            categories:
              allowed:
                - documentation
                - code
            models:
              llm:
                name: {selection["llm"].name}
                sha256: {selection["llm"].sha256}
                license: {selection["llm"].license}
              embedding:
                name: {selection["embedding"].name}
                sha256: {selection["embedding"].sha256}
                license: {selection["embedding"].license}
            """
        ).strip()
        self.policy_path.write_text(policy + "\n", encoding="utf-8")

    def _ensure_consent_ledger(self) -> None:
        if self.consent_ledger.exists():
            return
        metadata = {
            "type": "metadata",
            "version": 1,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "secret_hex": token_bytes(32).hex(),
        }
        self.consent_ledger.write_text(
            json.dumps(metadata, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Minimal TOML encoder (avoids external dependencies)
    # ------------------------------------------------------------------
    def _toml_dump(self, data: dict[str, Any]) -> str:
        lines: list[str] = []
        for section, values in sorted(data.items()):
            lines.append(f"[{section}]")
            for key, value in sorted(values.items()):
                formatted = self._format_value(value)
                lines.append(f"{key} = {formatted}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _format_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, Path):
            value = str(value)
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
            return f'"{escaped}"'
        raise TypeError(f"Unsupported TOML value: {value!r}")


__all__ = ["FirstRunConfigurator", "HardwareProfile"]

