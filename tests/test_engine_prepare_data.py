from app.core.engine import Engine
from app.data import pipeline
from app.core import engine as engine_module


def test_prepare_data_handles_list(monkeypatch, tmp_path):
    """Engine.prepare_data processes lists of raw datasets."""

    raw = [{"feedback": []}, {"feedback": []}]

    monkeypatch.setattr(pipeline, "load_raw_data", lambda: raw)

    validated: list[dict] = []
    monkeypatch.setattr(
        engine_module, "validate_feedback_schema", lambda d: validated.append(d)
    )

    cleaned: list[dict] = []
    monkeypatch.setattr(
        pipeline, "clean_data", lambda d: cleaned.append(d) or d
    )

    monkeypatch.setattr(
        pipeline, "transform_data", lambda d: tmp_path / "out.json"
    )

    engine = Engine()
    result = engine.prepare_data()

    assert validated == raw
    assert cleaned == raw
    assert result.endswith("out.json")

