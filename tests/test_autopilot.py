from __future__ import annotations

from datetime import datetime

import pytest

from app.autopilot import AutopilotError, AutopilotScheduler, ResourceProbe, ResourceUsage
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
    assert state.queue == ["docs"]
    assert state.current_topic == "docs"
    assert state.last_reason == "ok"
    assert engine.offline[-1] is False
    assert state.logs, "Logs should record activation"

    reloaded = AutopilotScheduler(
        policy_loader=_policy,
        state_path=tmp_path / "state.json",
        resource_probe=probe,
    )
    assert reloaded.state.queue == ["docs"]


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
