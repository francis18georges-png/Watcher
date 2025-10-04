"""Supervised autopilot scheduler enforcing policy constraints."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from app.policy.manager import PolicyError, PolicyManager
from app.policy.schema import DailyWindow, Policy

try:  # pragma: no cover - optional dependency
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback
    from app.utils import psutil_stub as psutil  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


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
class TopicScore:
    """Scoring metadata attached to a queued topic."""

    utility: float | None = None
    confidence: float | None = None
    cost: float | None = None

    def to_dict(self) -> dict[str, float]:
        payload: dict[str, float] = {}
        if self.utility is not None:
            payload["utility"] = float(self.utility)
        if self.confidence is not None:
            payload["confidence"] = float(self.confidence)
        if self.cost is not None:
            payload["cost"] = float(self.cost)
        return payload

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "TopicScore":
        if data is None:
            return cls()
        return cls(
            utility=_coerce_score(data.get("utility")),
            confidence=_coerce_score(data.get("confidence")),
            cost=_coerce_score(data.get("cost")),
        )

    def merge(self, other: "TopicScore") -> "TopicScore":
        return TopicScore(
            utility=other.utility if other.utility is not None else self.utility,
            confidence=other.confidence if other.confidence is not None else self.confidence,
            cost=other.cost if other.cost is not None else self.cost,
        )

    @property
    def utility_value(self) -> float:
        return float(self.utility) if self.utility is not None else 0.0

    @property
    def confidence_value(self) -> float:
        return float(self.confidence) if self.confidence is not None else 0.0

    @property
    def cost_value(self) -> float:
        return float(self.cost) if self.cost is not None else 0.0


@dataclass
class TopicQueueEntry:
    """Queue entry storing a topic alongside its scoring metadata."""

    topic: str
    score: TopicScore = field(default_factory=TopicScore)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"topic": self.topic}
        score_payload = self.score.to_dict()
        if score_payload:
            payload["score"] = score_payload
        return payload

    @classmethod
    def from_data(cls, data: Mapping[str, Any] | str) -> "TopicQueueEntry" | None:
        if isinstance(data, str):
            topic = data.strip()
            return cls(topic=topic) if topic else None
        topic_value = data.get("topic") or data.get("name")
        if topic_value is None:
            return None
        topic = str(topic_value).strip()
        if not topic:
            return None
        score_data = data.get("score") if isinstance(data.get("score"), Mapping) else data
        score = TopicScore.from_mapping(score_data if isinstance(score_data, Mapping) else None)
        return cls(topic=topic, score=score)

    def merge(self, other: "TopicQueueEntry") -> None:
        self.score = self.score.merge(other.score)

    @property
    def sort_key(self) -> tuple[float, float, float, str]:
        return (
            -self.score.utility_value,
            -self.score.confidence_value,
            self.score.cost_value,
            self.topic,
        )


@dataclass
class AutopilotState:
    """Persisted autopilot scheduler state."""

    enabled: bool = False
    online: bool = False
    queue: list[TopicQueueEntry] = field(default_factory=list)
    current_topic: str | None = None
    last_check: str | None = None
    last_reason: str | None = None
    logs: list[AutopilotLogEntry] = field(default_factory=list)
    last_cpu_percent: float | None = None
    last_ram_mb: float | None = None

    def __post_init__(self) -> None:
        self.queue = self._coerce_queue(self.queue)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "online": self.online,
            "queue": [entry.to_dict() for entry in self.queue],
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
            queue=cls._coerce_queue(data.get("queue", [])),
            current_topic=data.get("current_topic"),  # type: ignore[arg-type]
            last_check=data.get("last_check"),  # type: ignore[arg-type]
            last_reason=data.get("last_reason"),  # type: ignore[arg-type]
            logs=logs,
            last_cpu_percent=data.get("last_cpu_percent"),  # type: ignore[arg-type]
            last_ram_mb=data.get("last_ram_mb"),  # type: ignore[arg-type]
        )

    @staticmethod
    def _coerce_queue(value: object) -> list[TopicQueueEntry]:
        if not value:
            return []
        entries: list[TopicQueueEntry] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, TopicQueueEntry):
                    entries.append(item)
                    continue
                if isinstance(item, dict):
                    entry = TopicQueueEntry.from_data(item)
                elif isinstance(item, str):
                    entry = TopicQueueEntry.from_data(item)
                else:
                    entry = None
                if entry is not None:
                    entries.append(entry)
        return entries

    @property
    def topics(self) -> list[str]:
        return [entry.topic for entry in self.queue]


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
        topics: Sequence[object] | str,
        *,
        engine=None,
        now: datetime | None = None,
    ) -> AutopilotState:
        normalised = self._normalise_topics(topics)
        if not normalised:
            raise AutopilotError("aucun sujet fourni")
        existing = {entry.topic: entry for entry in self.state.queue}
        for entry in normalised:
            current = existing.get(entry.topic)
            if current is None:
                new_entry = TopicQueueEntry(
                    topic=entry.topic,
                    score=TopicScore(
                        utility=entry.score.utility,
                        confidence=entry.score.confidence,
                        cost=entry.score.cost,
                    ),
                )
                self.state.queue.append(new_entry)
                existing[entry.topic] = new_entry
            else:
                current.merge(entry)
        self._sort_queue()
        self.state.enabled = True
        self._log("info", f"Activation avec {', '.join(entry.topic for entry in normalised)}")
        return self.evaluate(engine=engine, now=now)

    def disable(
        self,
        topics: Sequence[object] | str | None = None,
        *,
        engine=None,
        now: datetime | None = None,
    ) -> AutopilotState:
        normalised = self._normalise_topics(topics) if topics else []
        if normalised:
            topics_to_remove = {entry.topic for entry in normalised}
            removed = {entry.topic for entry in self.state.queue if entry.topic in topics_to_remove}
            if removed:
                self._log("info", f"Sujets retirés: {', '.join(sorted(removed))}")
            self.state.queue = [
                entry for entry in self.state.queue if entry.topic not in topics_to_remove
            ]
        else:
            if self.state.queue:
                self._log("info", "File d'attente vidée.")
            self.state.queue.clear()
        self._sort_queue()
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
        kill_switch = policy.kill_switch_file
        if kill_switch.exists():
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
        allowed = self._is_within_window(policy.network_windows, now)
        budgets_ok = self._within_budgets(policy, usage)
        if self.state.queue:
            self.state.current_topic = self.state.queue[0].topic
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
            state.queue.sort(key=lambda entry: entry.sort_key)
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

    def _normalise_topics(self, topics: Sequence[object] | str | None) -> list[TopicQueueEntry]:
        if topics is None:
            return []

        entries: dict[str, TopicQueueEntry] = {}

        def _clone(entry: TopicQueueEntry) -> TopicQueueEntry:
            return TopicQueueEntry(
                topic=entry.topic,
                score=TopicScore(
                    utility=entry.score.utility,
                    confidence=entry.score.confidence,
                    cost=entry.score.cost,
                ),
            )

        def _merge(entry: TopicQueueEntry | None) -> None:
            if entry is None or not entry.topic:
                return
            existing = entries.get(entry.topic)
            if existing is None:
                entries[entry.topic] = _clone(entry)
            else:
                existing.merge(entry)

        def _handle_candidate(candidate: object) -> None:
            if isinstance(candidate, TopicQueueEntry):
                _merge(candidate)
                return
            if isinstance(candidate, str):
                for segment in candidate.split(","):
                    cleaned = segment.strip()
                    if cleaned:
                        _merge(TopicQueueEntry(topic=cleaned))
                return
            if isinstance(candidate, Mapping):
                _merge(TopicQueueEntry.from_data(candidate))
                return
            if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
                candidate_list = list(candidate)
                if not candidate_list:
                    return
                topic = str(candidate_list[0]).strip()
                if not topic:
                    return
                score_value = candidate_list[1] if len(candidate_list) > 1 else None
                if isinstance(score_value, TopicScore):
                    score = TopicScore(
                        utility=score_value.utility,
                        confidence=score_value.confidence,
                        cost=score_value.cost,
                    )
                elif isinstance(score_value, Mapping):
                    score = TopicScore.from_mapping(score_value)
                else:
                    score = TopicScore()
                _merge(TopicQueueEntry(topic=topic, score=score))
                return
            text = str(candidate).strip()
            if text:
                _merge(TopicQueueEntry(topic=text))

        if isinstance(topics, str):
            _handle_candidate(topics)
        else:
            for item in topics:
                _handle_candidate(item)

        return list(entries.values())

    def _sort_queue(self) -> None:
        self.state.queue.sort(key=lambda entry: entry.sort_key)

    def _is_within_window(
        self, windows: Mapping[str, DailyWindow], now: datetime
    ) -> bool:
        if not windows:
            return False
        weekday = now.strftime("%a").lower()[:3]
        current = now.time().replace(second=0, microsecond=0)
        window = windows.get(weekday)
        if window is None:
            return False
        return window.start <= current < window.end

    def _within_budgets(self, policy: Policy, usage: ResourceUsage) -> bool:
        cpu_ok = usage.cpu_percent <= policy.budgets.cpu_percent_cap
        ram_ok = usage.ram_mb <= policy.budgets.ram_mb_cap
        return cpu_ok and ram_ok

