import pytest

from app.core.critic import Critic


@pytest.mark.parametrize(
    "text",
    [
        "Merci pour votre aide",
        "S'il vous plaît, pourriez-vous aider?",
        "Bonjour, comment allez-vous?",
        "Salut, comment ça va?",
    ],
)
def test_french_politeness(text):
    critic = Critic()
    result = critic.evaluate(text)
    assert result["scores"]["politeness"] == 1.0
