"""Supervised autopilot scheduler enforcing policy constraints."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Callable, Iterable, Sequence

from app.policy.manager import PolicyError, PolicyManager
from app.policy.schema import Policy, TimeWindow, _parse_window

try:  # pragma: no cover - optional dependency
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback
    from app.utils import psutil_stub as psutil  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)


@dataclass
class ResourceUsage:
    """Snapshot of host resource usage."""

    cpu_percent: float
    ram_mb: float


class ResourceProbe:
    """Callable helper returning :class:`ResourceUsage` snapshots."""

    def snapshot(self) -> ResourceUsage:
        mem = psutil.virtual_memory()
        return ResourceUsage(
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            ram_mb=float(mem.used / (1024 * 1024)),
        )


@dataclass
class AutopilotLogEntry:
    """In-memory representation of a scheduler log entry."""

    timestamp: str
    level: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"timestamp": self.timestamp, "level": self.level, "message": self.message}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "AutopilotLogEntry":
        return cls(
            timestamp=str(data.get("timestamp", "")),
            level=str(data.get("level", "INFO")),
            message=str(data.get("message", "")),
        )


@dataclass
class AutopilotState:
    """Persisted autopilot scheduler state."""

    enabled: bool = False
    online: bool = False
    queue: list[str] = field(default_factory=list)
    current_topic: str | None = None
    last_check: str | None = None
    last_reason: str | None = None
    logs: list[AutopilotLogEntry] = field(default_factory=list)
    last_cpu_percent: float | None = None
    last_ram_mb: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "online": self.online,
            "queue": list(self.queue),
            "current_topic": self.current_topic,
            "last_check": self.last_check,
            "last_reason": self.last_reason,
            "logs": [entry.to_dict() for entry in self.logs],
            "last_cpu_percent": self.last_cpu_percent,
            "last_ram_mb": self.last_ram_mb,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AutopilotState":
        logs = [
            AutopilotLogEntry.from_dict(item)
            for item in data.get("logs", [])  # type: ignore[arg-type]
        ]
        return cls(
            enabled=bool(data.get("enabled", False)),
            online=bool(data.get("online", False)),
            queue=list(data.get("queue", [])),  # type: ignore[arg-type]
            current_topic=data.get("current_topic"),  # type: ignore[arg-type]
            last_check=data.get("last_check"),  # type: ignore[arg-type]
            last_reason=data.get("last_reason"),  # type: ignore[arg-type]
            logs=logs,
            last_cpu_percent=data.get("last_cpu_percent"),  # type: ignore[arg-type]
            last_ram_mb=data.get("last_ram_mb"),  # type: ignore[arg-type]
        )


class AutopilotError(RuntimeError):
    """Raised when the autopilot scheduler cannot continue."""


class AutopilotScheduler:
    """Plan and toggle network access according to the user policy."""

    def __init__(
        self,
        *,
        policy_loader: Callable[[], Policy] | None = None,
        policy_manager: PolicyManager | None = None,
        state_path: Path | None = None,
        resource_probe: ResourceProbe | None = None,
        clock: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if policy_loader is None:
            if policy_manager is None:
                policy_manager = PolicyManager()
            policy_loader = policy_manager._read_policy
        self._policy_loader = policy_loader
        self._policy_manager = policy_manager
        if state_path is None:
            base_dir = (
                policy_manager.config_dir
                if policy_manager is not None
                else Path.home() / ".watcher"
            )
            state_path = base_dir / "autopilot-state.json"
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._resource_probe = resource_probe or ResourceProbe()
        self._clock = clock or datetime.utcnow
        self._logger = logger or LOGGER
        self.state = self._load_state()

    # ------------------------------------------------------------------
    # Public API

    def enable(
        self,
        topics: Sequence[str] | str,
        *,
        engine=None,
        now: datetime | None = None,
    ) -> AutopilotState:
        normalised = self._normalise_topics(topics)
        if not normalised:
            raise AutopilotError("aucun sujet fourni")
        for topic in normalised:
            if topic not in self.state.queue:
                self.state.queue.append(topic)
        self.state.enabled = True
        self._log("info", f"Activation avec {', '.join(normalised)}")
        return self.evaluate(engine=engine, now=now)

    def disable(
        self,
        topics: Sequence[str] | str | None = None,
        *,
        engine=None,
        now: datetime | None = None,
    ) -> AutopilotState:
        normalised = self._normalise_topics(topics) if topics else []
        if normalised:
            removed = {topic for topic in normalised if topic in self.state.queue}
            if removed:
                self._log("info", f"Sujets retirés: {', '.join(sorted(removed))}")
            self.state.queue = [topic for topic in self.state.queue if topic not in removed]
        else:
            if self.state.queue:
                self._log("info", "File d'attente vidée.")
            self.state.queue.clear()
        if self.state.enabled:
            self.state.enabled = False
            self.state.online = False
            self.state.current_topic = None
            self.state.last_reason = "désactivé"
            self._log("info", "Autopilot désactivé.")
        now = now or self._clock()
        self.state.last_check = self._timestamp(now)
        self._save_state()
        if engine is not None:
            engine.set_offline(True)
        return self.state

    def evaluate(
        self,
        *,
        engine=None,
        now: datetime | None = None,
    ) -> AutopilotState:
        now = now or self._clock()
        self.state.last_check = self._timestamp(now)
        if not self.state.enabled:
            self.state.online = False
            self.state.current_topic = None
            self.state.last_reason = "désactivé"
            if engine is not None:
                engine.set_offline(True)
            self._save_state()
            return self.state
        try:
            policy = self._policy_loader()
        except PolicyError as exc:
            message = f"policy.yaml invalide: {exc}"
            self._log("error", message)
            self.state.enabled = False
            self.state.online = False
            self.state.last_reason = "policy introuvable"
            self.state.current_topic = None
            self._save_state()
            if engine is not None:
                engine.set_offline(True)
            raise AutopilotError(message) from exc
        if policy.defaults.kill_switch:
            if self.state.enabled:
                self._log("warning", "Kill-switch activé – autopilot suspendu.")
            self.state.enabled = False
            self.state.online = False
            self.state.current_topic = None
            self.state.last_reason = "kill-switch"
            self._save_state()
            if engine is not None:
                engine.set_offline(True)
            return self.state
        usage = self._resource_probe.snapshot()
        self.state.last_cpu_percent = usage.cpu_percent
        self.state.last_ram_mb = usage.ram_mb
        allowed = self._is_within_window(policy.network.allowed_windows, now)
        budgets_ok = self._within_budgets(policy, usage)
        if self.state.queue:
            self.state.current_topic = self.state.queue[0]
        else:
            self.state.current_topic = None
        reason = None
        should_online = allowed and budgets_ok and bool(self.state.queue)
        if not allowed:
            reason = "hors fenêtre réseau"
        elif not budgets_ok:
            reason = "budgets dépassés"
        elif not self.state.queue:
            reason = "file d'attente vide"
        if should_online:
            if not self.state.online:
                self._log("info", "Autopilot en ligne – exécution autorisée.")
            self.state.online = True
            self.state.last_reason = "ok"
            if engine is not None:
                engine.set_offline(False)
        else:
            if self.state.online or self.state.last_reason != reason:
                level = "info" if reason == "file d'attente vide" else "warning"
                self._log(level, f"Autopilot hors ligne ({reason}).")
            self.state.online = False
            self.state.last_reason = reason
            self.state.current_topic = None if reason != "file d'attente vide" else self.state.current_topic
            if engine is not None:
                engine.set_offline(True)
        self._save_state()
        return self.state

    # ------------------------------------------------------------------
    # Helpers

    def _load_state(self) -> AutopilotState:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = AutopilotState.from_dict(data)
            return state
        state = AutopilotState()
        self._save_state(state)
        return state

    def _save_state(self, state: AutopilotState | None = None) -> None:
        state = state or self.state
        payload = state.to_dict()
        self.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _log(self, level: str, message: str) -> None:
        timestamp = self._timestamp(self._clock())
        entry = AutopilotLogEntry(timestamp=timestamp, level=level.upper(), message=message)
        self.state.logs.append(entry)
        if len(self.state.logs) > 100:
            self.state.logs = self.state.logs[-100:]
        level_value = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(level_value, message)

    def _timestamp(self, value: datetime) -> str:
        return value.replace(microsecond=0).isoformat()

    def _normalise_topics(self, topics: Sequence[str] | str | None) -> list[str]:
        if topics is None:
            return []
        if isinstance(topics, str):
            raw_items: Iterable[str] = topics.split(",")
        else:
            raw_items = []
            for topic in topics:
                raw_items.extend(str(topic).split(","))
        cleaned: list[str] = []
        for item in raw_items:
            normalised = item.strip()
            if not normalised:
                continue
            if normalised not in cleaned:
                cleaned.append(normalised)
        return cleaned

    def _is_within_window(self, windows: Sequence[TimeWindow], now: datetime) -> bool:
        if not windows:
            return False
        weekday = now.strftime("%a").lower()[:3]
        current = now.time().replace(second=0, microsecond=0)
        for window in windows:
            if weekday not in window.days:
                continue
            start, end = self._parse_window(window.window)
            if start <= current < end:
                return True
        return False

    def _parse_window(self, value: str) -> tuple[time, time]:
        start, end = _parse_window(value)
        return start, end

    def _within_budgets(self, policy: Policy, usage: ResourceUsage) -> bool:
        cpu_ok = usage.cpu_percent <= policy.budgets.cpu_percent
        ram_ok = usage.ram_mb <= policy.budgets.ram_mb
        return cpu_ok and ram_ok

