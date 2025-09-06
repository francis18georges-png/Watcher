import pytest

from app.core.critic import Critic


@pytest.mark.parametrize(
    "text", ["Merci pour votre aide", "S'il vous plaît, pourriez-vous aider?"]
)
def test_french_politeness(text):
    critic = Critic()
    result = critic.evaluate(text)
    assert result["scores"]["politeness"] == 1.0
