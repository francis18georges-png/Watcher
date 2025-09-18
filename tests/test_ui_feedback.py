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


def test_rate_records_high_value(monkeypatch):
    errors: list[tuple[str, str]] = []

    monkeypatch.setattr(main.messagebox, "showerror", lambda title, msg: errors.append((title, msg)))

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
