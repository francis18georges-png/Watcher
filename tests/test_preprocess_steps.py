from app.data import pipeline as dp
from app.data.preprocess import HtmlCleaner, SimpleTokenizer


def fake_config(section=None):
    if section == "data":
        return {
            "steps": {
                "clean": "app.data.preprocess.cleaning.HtmlCleaner",
                "tokenize": "app.data.preprocess.tokenizer.SimpleTokenizer",
            }
        }
    return {}


def test_cleaner_and_tokenizer(monkeypatch):
    monkeypatch.setattr(dp, "load_config", fake_config)
    text = "<p>Hello world!</p>"
    result = dp.run_pipeline(text)
    assert result == ["hello", "world"]


def test_modules_callable():
    cleaner = HtmlCleaner()
    tokenizer = SimpleTokenizer()
    cleaned = cleaner("<b>Salut\n monde</b>")
    assert cleaned == "Salut monde"
    tokens = tokenizer(cleaned)
    assert tokens == ["salut", "monde"]
