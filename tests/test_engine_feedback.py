import pytest

from app.core.engine import Engine
from app.core.memory import Memory


def _make_engine(tmp_path):
    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.mem.set_offline(False)
    eng.last_prompt = "question"
    eng.last_answer = "answer"
    return eng


def test_add_feedback_accepts_valid_rating(tmp_path):
    eng = _make_engine(tmp_path)
    msg = eng.add_feedback(0.5)
    assert msg == "feedback enregistré"
    kind, prompt, answer, rating = eng.mem.all_feedback()[0]
    assert (kind, prompt, answer, rating) == ("chat", "question", "answer", 0.5)


def test_add_feedback_rejects_out_of_range_rating(tmp_path):
    eng = _make_engine(tmp_path)
    with pytest.raises(ValueError):
        eng.add_feedback(1.5)
