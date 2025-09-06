from app.config import load_config


def test_load_existing_section():
    cfg = load_config("llm")
    assert cfg["model"] == "llama3.2:3b"
    assert cfg["backend"] == "ollama"


def test_load_missing_section():
    assert load_config("does_not_exist") == {}
