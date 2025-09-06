import math

from app.core.critic import Critic


def test_high_score_passes():
    critic = Critic(threshold=0.8)
    text = "please " + "word " * 100 + "thank you"
    result = critic.evaluate(text)
    assert math.isclose(result["score"], 1.0, abs_tol=1e-6)
    assert result["passed"] is True


def test_weighting_affects_score():
    critic = Critic(weights={"length": 0.1, "politeness": 0.9})
    text = "please hello"
    result = critic.evaluate(text)
    # length is 0.02, politeness 1.0 -> score ~0.902
    assert result["score"] > 0.9
    assert result["scores"]["politeness"] == 1.0


def test_threshold_triggers_failure():
    critic = Critic(threshold=0.7)
    text = "word " * 10
    result = critic.evaluate(text)
    assert result["score"] < critic.threshold
    assert result["passed"] is False
