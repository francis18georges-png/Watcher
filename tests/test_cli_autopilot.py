from types import SimpleNamespace

import pytest

from app import cli
from app.autopilot import AutopilotState


class DummyEngine:
    def __init__(self) -> None:
        self.offline: list[bool] = []

    def set_offline(self, value: bool) -> None:  # pragma: no cover - executed in tests
        self.offline.append(bool(value))


class DummyScheduler:
    def __init__(
        self,
        *,
        enable_state: AutopilotState | None = None,
        disable_state: AutopilotState | None = None,
        evaluate_state: AutopilotState | None = None,
    ) -> None:
        self.enable_calls: list[list[str]] = []
        self.disable_calls: list[list[str] | None] = []
        self.evaluate_calls = 0
        self._enable_state = enable_state or AutopilotState(enabled=True, online=True, queue=["foo"], last_reason="ok")
        self._disable_state = disable_state or AutopilotState(enabled=False, online=False, queue=[])
        self._evaluate_state = evaluate_state or self._enable_state

    def enable(self, topics, *, engine=None, now=None):  # pragma: no cover - executed in tests
        values = list(topics)
        self.enable_calls.append(values)
        if engine is not None:
            engine.set_offline(not self._enable_state.online)
        state = AutopilotState(**self._enable_state.to_dict())
        state.queue = list(values)
        state.current_topic = values[0] if values else None
        return state

    def disable(self, topics=None, *, engine=None, now=None):  # pragma: no cover - executed in tests
        values = list(topics) if topics else None
        self.disable_calls.append(values)
        if engine is not None:
            engine.set_offline(True)
        return AutopilotState(**self._disable_state.to_dict())

    def evaluate(self, *, engine=None, now=None):  # pragma: no cover - executed in tests
        self.evaluate_calls += 1
        if engine is not None:
            engine.set_offline(not self._evaluate_state.online)
        return AutopilotState(**self._evaluate_state.to_dict())


@pytest.fixture(autouse=True)
def _stub_cli_settings(monkeypatch):
    settings = SimpleNamespace(
        llm=SimpleNamespace(backend="stub", model="stub-model"),
        training=SimpleNamespace(seed=42),
        intelligence=SimpleNamespace(mode="offline"),
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    return settings


def test_cli_autopilot_enable(monkeypatch, capsys):
    engine = DummyEngine()
    enable_state = AutopilotState(enabled=True, online=True, queue=["foo", "bar"], last_reason="ok")
    scheduler = DummyScheduler(enable_state=enable_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "enable", "--topics", "foo,bar"])

    assert exit_code == 0
    assert scheduler.enable_calls == [["foo", "bar"]]
    assert engine.offline[-1] is False
    captured = capsys.readouterr()
    assert "Autopilot activé (en ligne)" in captured.out
    assert "foo, bar" in captured.out


def test_cli_autopilot_status_offline(monkeypatch, capsys):
    engine = DummyEngine()
    status_state = AutopilotState(enabled=True, online=False, queue=["foo"], last_reason="hors fenêtre réseau")
    scheduler = DummyScheduler(evaluate_state=status_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "status", "--topics", "bar"])

    assert exit_code == 0
    assert scheduler.evaluate_calls == 1
    assert engine.offline[-1] is True
    captured = capsys.readouterr()
    assert "Autopilot hors ligne (hors fenêtre réseau)" in captured.out
    assert "Sujets absents de la file: bar" in captured.out


def test_cli_autopilot_disable(monkeypatch, capsys):
    engine = DummyEngine()
    disable_state = AutopilotState(enabled=False, online=False, queue=[])
    scheduler = DummyScheduler(disable_state=disable_state)
    monkeypatch.setattr(cli, "AutopilotScheduler", lambda: scheduler)
    monkeypatch.setattr(cli, "Engine", lambda: engine)

    exit_code = cli.main(["autopilot", "disable"])

    assert exit_code == 0
    assert scheduler.disable_calls == [None]
    assert engine.offline[-1] is True
    captured = capsys.readouterr()
    assert "Autopilot désactivé" in captured.out
