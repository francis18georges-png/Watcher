from config import load_config


def test_dev_profile():
    cfg = load_config(profile="dev")
    assert cfg["ui"]["mode"] == "dev"
    assert cfg["ui"]["theme"] == "dark"


def test_prod_profile():
    cfg = load_config(profile="prod")
    assert cfg["ui"]["mode"] == "prod"
    assert cfg["ui"]["theme"] == "dark"
