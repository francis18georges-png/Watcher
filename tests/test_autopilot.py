from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.autopilot import (
    AutopilotError,
    AutopilotScheduler,
    ResourceProbe,
    ResourceUsage,
    TopicQueueEntry,
    TopicScore,
)
from app.policy.schema import (
    Budgets,
    Categories,
    Defaults,
    ModelEntry,
    ModelsSection,
    NetworkSection,
    Policy,
    Subject,
    TimeWindow,
)


class DummyEngine:
    def __init__(self) -> None:
        self.offline: list[bool] = []

    def set_offline(self, value: bool) -> None:  # pragma: no cover - executed in tests
        self.offline.append(bool(value))


class DummyProbe(ResourceProbe):
    def __init__(self, usage: ResourceUsage) -> None:
        self._usage = usage

    def snapshot(self) -> ResourceUsage:  # pragma: no cover - executed in tests
        return self._usage

    def set_usage(self, usage: ResourceUsage) -> None:
        self._usage = usage


def _policy() -> Policy:
    now = datetime(2024, 1, 1, 10, 0, 0)
    return Policy(
        version=1,
        subject=Subject(hostname="test-host", generated_at=now),
        defaults=Defaults(),
        network=NetworkSection(
            allowed_windows=[TimeWindow(days=["mon", "tue"], window="08:00-20:00")],
            bandwidth_mb=500,
            time_budget_minutes=120,
            allowlist=[],
        ),
        budgets=Budgets(cpu_percent=50, ram_mb=1024),
        categories=Categories(allowed=[]),
        models=ModelsSection(
            llm=ModelEntry(name="llm", sha256="abc", license="MIT"),
            embedding=ModelEntry(name="embed", sha256="def", license="MIT"),
        ),
    )


def test_scheduler_enables_and_tracks_queue(tmp_path):
    usage = ResourceUsage(cpu_percent=10, ram_mb=256)
    probe = DummyProbe(usage)
    engine = DummyEngine()
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    state = scheduler.enable(["docs"], engine=engine, now=datetime(2024, 1, 1, 10, 0, 0))

    assert state.enabled is True
    assert state.online is True
    assert state.topics == ["docs"]
    assert state.queue[0].score.utility is None
    assert state.current_topic == "docs"
    assert state.last_reason == "ok"
    assert engine.offline[-1] is False
    assert state.logs, "Logs should record activation"

    reloaded = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )
    assert reloaded.state.topics == ["docs"]


def test_scheduler_respects_time_windows(tmp_path):
    usage = ResourceUsage(cpu_percent=10, ram_mb=256)
    probe = DummyProbe(usage)
    engine = DummyEngine()
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    scheduler.enable(["docs"], engine=engine, now=datetime(2024, 1, 1, 9, 0, 0))
    state = scheduler.evaluate(engine=engine, now=datetime(2024, 1, 1, 22, 0, 0))

    assert state.online is False
    assert state.last_reason == "hors fenêtre réseau"
    assert engine.offline[-1] is True


def test_scheduler_time_window_locale_independent(tmp_path, monkeypatch):
    usage = ResourceUsage(cpu_percent=10, ram_mb=256)
    probe = DummyProbe(usage)
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    class FrenchLocaleDatetime(datetime):
        def strftime(self, fmt: str) -> str:  # pragma: no cover - patched in test
            if fmt == "%a":
                return "lun"
            return super().strftime(fmt)

    monkeypatch.setattr("app.autopilot.scheduler.datetime", FrenchLocaleDatetime)

    now = FrenchLocaleDatetime(2024, 1, 1, 10, 0, 0)

    state = scheduler.enable(["docs"], now=now)

    assert state.online is True
    assert state.last_reason == "ok"

    follow_up = scheduler.evaluate(now=FrenchLocaleDatetime(2024, 1, 1, 12, 0, 0))

    assert follow_up.online is True
    assert follow_up.last_reason == "ok"


def test_scheduler_respects_resource_budgets(tmp_path):
    probe = DummyProbe(ResourceUsage(cpu_percent=10, ram_mb=256))
    engine = DummyEngine()
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    scheduler.enable(["docs"], engine=engine, now=datetime(2024, 1, 1, 10, 0, 0))
    probe.set_usage(ResourceUsage(cpu_percent=80, ram_mb=256))
    state = scheduler.evaluate(engine=engine, now=datetime(2024, 1, 1, 10, 5, 0))

    assert state.online is False
    assert state.last_reason == "budgets dépassés"
    assert engine.offline[-1] is True


def test_enable_requires_topics(tmp_path):
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=DummyProbe(ResourceUsage(cpu_percent=10, ram_mb=256)),
    )

    with pytest.raises(AutopilotError):
        scheduler.enable([], now=datetime(2024, 1, 1, 10, 0, 0))


def test_scheduler_prioritises_and_merges_scores(tmp_path):
    probe = DummyProbe(ResourceUsage(cpu_percent=5, ram_mb=128))
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    priorities = [
        {"topic": "baseline", "score": {"utility": 0.6, "confidence": 0.5, "cost": 4}},
        {"topic": "urgent", "score": {"utility": 0.9, "confidence": 0.6, "cost": 3}},
        {"topic": "critical", "score": {"utility": 0.9, "confidence": 0.8, "cost": 5}},
        {"topic": "cheap", "score": {"utility": 0.9, "confidence": 0.8, "cost": 1}},
    ]

    state = scheduler.enable(priorities, now=datetime(2024, 1, 1, 10, 0, 0))

    assert state.topics == ["cheap", "critical", "urgent", "baseline"]

    scheduler.enable(
        [
            ("baseline", TopicScore(utility=0.95, confidence=0.9, cost=2)),
            {"topic": "critical", "score": {"cost": 0.5}},
        ],
        now=datetime(2024, 1, 1, 10, 5, 0),
    )

    assert scheduler.state.topics == ["baseline", "critical", "cheap", "urgent"]
    assert scheduler.state.queue[0].score.utility == pytest.approx(0.95)
    assert scheduler.state.queue[1].score.cost == pytest.approx(0.5)


def test_disable_removes_topics_and_preserves_queue(tmp_path):
    probe = DummyProbe(ResourceUsage(cpu_percent=5, ram_mb=128))
    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )

    scheduler.enable(
        [
            {"topic": "keep", "score": {"utility": 0.5}},
            {"topic": "drop", "score": {"utility": 0.4}},
            "extra",
        ],
        now=datetime(2024, 1, 1, 10, 0, 0),
    )

    scheduler.disable(["drop"], now=datetime(2024, 1, 1, 10, 30, 0))

    assert [entry.topic for entry in scheduler.state.queue] == ["keep", "extra"]
    assert all(isinstance(entry, TopicQueueEntry) for entry in scheduler.state.queue)


def test_scheduler_migrates_legacy_queue(tmp_path):
    state_path = tmp_path / "state.json"
    legacy_state = {
        "enabled": True,
        "online": False,
        "queue": ["foo", "bar"],
        "logs": [],
    }
    state_path.write_text(json.dumps(legacy_state), encoding="utf-8")

    scheduler = AutopilotScheduler(
        policy_loader=_policy,
        state_path=state_path,
        resource_probe=DummyProbe(ResourceUsage(cpu_percent=5, ram_mb=128)),
    )

    assert scheduler.state.topics == ["bar", "foo"]
    assert all(isinstance(entry.score, TopicScore) for entry in scheduler.state.queue)

    scheduler._save_state()

    upgraded = json.loads(state_path.read_text(encoding="utf-8"))
    assert upgraded["queue"][0]["topic"] in {"bar", "foo"}
    assert isinstance(upgraded["queue"][0], dict)
