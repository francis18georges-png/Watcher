"""Utilities used to perform the first run auto-configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path
from secrets import token_bytes
from typing import Any

import hashlib
import json
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import textwrap

import yaml
from app.core.model_registry import ensure_models, select_models
from app.policy.ledger import ConsentLedger, LedgerError

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
        self.consent_ledger = self.config_dir / "consents.jsonl"
        self._legacy_consent_ledger = self.config_dir / "consent-ledger.jsonl"
        self.env_path = self.config_dir / ".env"
        self.sentinel_path = self.config_dir / "first_run"

    # ------------------------------------------------------------------
    # Configuration state helpers
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        """Return :data:`True` when the user environment already exists."""

        return self.config_path.exists() and self.policy_path.exists()

    def ensure_pending(self) -> None:
        """Create the first-run sentinel when configuration is missing."""

        if self.is_configured() or self.sentinel_path.exists():
            return

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.sentinel_path.write_text("pending\n", encoding="utf-8")

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
        self,
        *,
        auto: bool | None = None,
        fully_auto: bool | None = None,
        download_models: bool = True,
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

        if auto is None:
            auto = fully_auto if fully_auto is not None else True

        profile = self.detect_hardware()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        selection = select_models(profile.cpu_threads, profile.has_gpu)
        model_paths = self._ensure_model_paths(selection, download_models)

        self._write_config(profile, selection, model_paths)
        self._write_policy(selection)
        self._migrate_legacy_consent_ledger()
        self._ensure_consent_ledger()
        self._write_env(selection, model_paths)
        self._record_initial_consent()
        self._configure_autostart()

        if self.sentinel_path.exists():
            self.sentinel_path.unlink(missing_ok=True)

        return self.config_path

    # ------------------------------------------------------------------
    # File writers
    # ------------------------------------------------------------------
    def _ensure_model_paths(
        self, selection: dict[str, Any], download_models: bool
    ) -> dict[str, Path]:
        models_dir = self.config_dir / "models"
        llm_dir = models_dir / "llm"
        emb_dir = models_dir / "embeddings"

        if download_models:
            llm_path = ensure_models(llm_dir, [selection["llm"]])[0]
            emb_path = ensure_models(emb_dir, [selection["embedding"]])[0]
        else:
            llm_path = selection["llm"].destination(llm_dir)
            emb_path = selection["embedding"].destination(emb_dir)
            llm_path.parent.mkdir(parents=True, exist_ok=True)
            emb_path.parent.mkdir(parents=True, exist_ok=True)

        return {"llm": llm_path, "embedding": emb_path}

    def _write_config(
        self,
        profile: HardwareProfile,
        selection: dict[str, Any],
        model_paths: dict[str, Path],
    ) -> None:
        data_dir = self.config_dir / "data"
        models_dir = self.config_dir / "models"

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
                "model_path": str(model_paths["llm"]),
                "model_sha256": selection["llm"].sha256,
                "model_license": selection["llm"].license,
            },
            "memory": {
                "db_path": str(self.config_dir / "memory" / "mem.db"),
                "embed_model_path": str(model_paths["embedding"]),
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

    def _load_baseline_policy(self) -> dict[str, Any]:
        baseline = resources.files("config").joinpath("policy.yaml")
        with baseline.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        if not isinstance(data, dict):
            msg = "config/policy.yaml must contain a YAML mapping"
            raise TypeError(msg)
        return data

    def _write_policy(self, selection: dict[str, Any]) -> None:
        if self.policy_path.exists():
            return

        hostname = platform.node() or "localhost"
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        policy = self._load_baseline_policy()

        subject = policy.setdefault("subject", {})
        subject["hostname"] = hostname
        subject["generated_at"] = now

        models = policy.setdefault("models", {})
        llm = models.setdefault("llm", {})
        llm.update(
            name=selection["llm"].name,
            sha256=selection["llm"].sha256,
            license=selection["llm"].license,
        )
        embedding = models.setdefault("embedding", {})
        embedding.update(
            name=selection["embedding"].name,
            sha256=selection["embedding"].sha256,
            license=selection["embedding"].license,
        )

        rendered = yaml.safe_dump(policy, sort_keys=False)
        self.policy_path.write_text(rendered, encoding="utf-8")

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

    def _migrate_legacy_consent_ledger(self) -> None:
        """Move ``consent-ledger.jsonl`` to the new canonical name."""

        if not self._legacy_consent_ledger.exists():
            return
        if self.consent_ledger.exists():
            return

        try:
            self._legacy_consent_ledger.replace(self.consent_ledger)
        except OSError:
            # If the rename fails we fall back to leaving the legacy file in
            # place so that follow-up calls can still succeed.
            pass

    def _write_env(
        self, selection: dict[str, Any], model_paths: dict[str, Path]
    ) -> None:
        policy_hash = self._hash_path(self.policy_path)
        ledger_hash = self._hash_path(self.consent_ledger)

        values = {
            "WATCHER_ENV": "production",
            "WATCHER_HOME": str(self.config_dir),
            "WATCHER_CONFIG_PATH": str(self.config_path),
            "WATCHER_POLICY_PATH": str(self.policy_path),
            "WATCHER_CONSENT_LEDGER": str(self.consent_ledger),
            "WATCHER_LLM__MODEL_PATH": str(model_paths["llm"]),
            "WATCHER_LLM__MODEL_SHA256": selection["llm"].sha256,
            "WATCHER_MEMORY__EMBED_MODEL_PATH": str(model_paths["embedding"]),
            "WATCHER_MEMORY__EMBED_MODEL_SHA256": selection["embedding"].sha256,
            "WATCHER_POLICY__SHA256": policy_hash,
            "WATCHER_CONSENT__SHA256": ledger_hash,
        }

        lines = ["# Auto-generated by Watcher – do not edit manually."]
        for key in sorted(values):
            lines.append(f"{key}={values[key]}")
        lines.append("")
        self.env_path.write_text("\n".join(lines), encoding="utf-8")
        try:
            self.env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def _record_initial_consent(self) -> None:
        if not self.policy_path.exists() or not self.consent_ledger.exists():
            return

        content = self.consent_ledger.read_text(encoding="utf-8")
        if "\n" in content:
            lines = [line for line in content.splitlines() if line.strip()]
        else:
            lines = [content.strip()] if content.strip() else []
        if any('"action": "init"' in line for line in lines[1:]):
            return

        try:
            ledger = ConsentLedger(self.consent_ledger)
        except LedgerError:
            return

        ledger.record(
            action="init",
            domain="*",
            scope="bootstrap",
            policy_hash=self._hash_path(self.policy_path),
        )

    def _hash_path(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    # ------------------------------------------------------------------
    # Migration helpers
    # ------------------------------------------------------------------
    def migrate_legacy_state(self) -> None:
        """Run migrations for legacy configuration files."""

        self._migrate_legacy_consent_ledger()

    # ------------------------------------------------------------------
    # Autostart helpers
    # ------------------------------------------------------------------
    def _configure_autostart(self) -> None:
        """Install OS-specific autostart configuration for the autopilot."""

        if not self._should_enable_autostart():
            return

        system = platform.system()
        if system == "Windows":
            self._configure_windows_autostart()
        elif system in {"Linux", "FreeBSD"}:
            self._configure_systemd_autostart()

    def _should_enable_autostart(self) -> bool:
        """Return :data:`True` when the autopilot autostart is enabled."""

        if os.environ.get("WATCHER_DISABLE"):
            return False

        kill_switch = self.config_dir / "disable"
        if kill_switch.exists():
            return False

        value = os.environ.get("WATCHER_AUTOSTART")
        if value is None:
            return True

        value = value.strip().lower()
        return value not in {"", "0", "false", "no", "off"}

    def _autopilot_command_parts(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            "app.cli",
            "autopilot",
            "run",
            "--noninteractive",
        ]

    def _configure_windows_autostart(self) -> None:
        run_once_command = subprocess.list2cmdline(["watcher", "init", "--auto"])
        autopilot_command = subprocess.list2cmdline(
            ["watcher", "autopilot", "run", "--noninteractive"]
        )

        script_value = run_once_command.replace("'", "''")
        powershell_script = textwrap.dedent(
            f"""
            $path = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce'
            New-Item -Path $path -Force | Out-Null
            Set-ItemProperty -Path $path -Name 'WatcherInit' -Type String -Value '{script_value}' -Force
            """
        ).strip()

        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    powershell_script,
                ],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass

        try:
            subprocess.run(
                [
                    "schtasks",
                    "/Create",
                    "/TN",
                    "Watcher Autopilot",
                    "/TR",
                    autopilot_command,
                    "/SC",
                    "ONLOGON",
                    "/F",
                ],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass

    def _configure_systemd_autostart(self) -> None:
        systemd_dir = self.home / ".config" / "systemd" / "user"
        systemd_dir.mkdir(parents=True, exist_ok=True)

        service_path = systemd_dir / "watcher-autopilot.service"
        timer_path = systemd_dir / "watcher-autopilot.timer"

        command = shlex.join(self._autopilot_command_parts())

        service_body = textwrap.dedent(
            f"""
            [Unit]
            Description=Watcher Autopilot orchestrator

            [Service]
            Type=oneshot
            WorkingDirectory={self.home}
            Environment=WATCHER_HOME={self.config_dir}
            ExecStart={command}

            [Install]
            WantedBy=default.target
            """
        ).strip()
        service_path.write_text(
            "\n".join(line.rstrip() for line in service_body.splitlines()) + "\n",
            encoding="utf-8",
        )

        timer_body = textwrap.dedent(
            """
            [Unit]
            Description=Watcher Autopilot orchestrator schedule

            [Timer]
            OnBootSec=30s
            OnUnitActiveSec=1h
            Persistent=true
            Unit=watcher-autopilot.service

            [Install]
            WantedBy=timers.target
            """
        ).strip()
        timer_path.write_text(
            "\n".join(line.rstrip() for line in timer_body.splitlines()) + "\n",
            encoding="utf-8",
        )

        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass

        try:
            subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "enable",
                    "--now",
                    "watcher-autopilot.timer",
                ],
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass

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

