from pathlib import Path


def test_ethics_mentions_feedback_retention():
    content = Path("ETHICS.md").read_text(encoding="utf-8")
    assert "Conservation et effacement des retours" in content


def test_readme_mentions_confidentiality():
    content = Path("README.md").read_text(encoding="utf-8")
    assert "## Confidentialité" in content
