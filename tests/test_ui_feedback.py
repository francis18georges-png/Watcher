import tkinter as tk

import pytest

from app.ui import main


class _DummyText:
    def __init__(self) -> None:
        self.buffer: list[tuple[str, str]] = []
        self.last_seen: str | None = None

    def insert(self, index: str, text: str) -> None:
        self.buffer.append((index, text))

    def see(self, index: str) -> None:
        self.last_seen = index


class _DummyEngine:
    def __init__(self) -> None:
        self.recorded: list[float] = []

    def add_feedback(self, rating: float) -> str:
        self.recorded.append(rating)
        return "feedback enregistré"


class _DummyButton:
    def __init__(self) -> None:
        self.kwargs: dict[str, str] = {}

    def config(self, **kwargs) -> None:
        self.kwargs.update(kwargs)


class _DummyOfflineClient:
    def __init__(self) -> None:
        self.host = "mock-backend"
        self.model = "mock-model"
        self.offline = False

    def set_offline(self, value: bool) -> None:
        self.offline = value


class _DummyOfflineEngine:
    def __init__(self) -> None:
        self.offline_mode = False
        self.client = _DummyOfflineClient()

    def add_feedback(self, rating: float) -> str:  # pragma: no cover - compat
        return ""

    def set_offline_mode(self, enabled: bool) -> str:
        self.offline_mode = enabled
        self.client.set_offline(enabled)
        return f"mode offline {'activé' if enabled else 'désactivé'}"

    def plugin_metrics(self) -> list[dict[str, float | None]]:  # pragma: no cover
        return []


def test_rate_records_high_value(monkeypatch):
    errors: list[tuple[str, str]] = []

    monkeypatch.setattr(
        main.messagebox, "showerror", lambda title, msg: errors.append((title, msg))
    )

    app = main.WatcherApp.__new__(main.WatcherApp)
    app.engine = _DummyEngine()
    app.rate_var = tk.DoubleVar(master=tk.Tcl(), value=1.0)
    app.out = _DummyText()

    app._rate()

    assert len(app.engine.recorded) == 1
    assert app.engine.recorded[0] == pytest.approx(1.0)
    assert errors == []
    assert any(
        entry.strip().endswith("feedback enregistré") for _, entry in app.out.buffer
    )


def test_toggle_offline_updates_status(monkeypatch):
    monkeypatch.setattr(main.WatcherApp, "_refresh_plugin_metrics", lambda self: None)

    app = main.WatcherApp.__new__(main.WatcherApp)
    app.engine = _DummyOfflineEngine()
    app.status_var = tk.StringVar(master=tk.Tcl())
    app.offline_btn = _DummyButton()
    app.out = _DummyText()
    app._plugin_rows = {}

    main.WatcherApp._update_status_label(app)
    assert "Mode: Sur" in app.status_var.get()

    app._toggle_offline()

    assert app.engine.offline_mode is True
    assert "activé" in app.offline_btn.kwargs.get("text", "")
    assert "Hors ligne" in app.status_var.get()
    assert any("mode offline" in text.lower() for _, text in app.out.buffer)
