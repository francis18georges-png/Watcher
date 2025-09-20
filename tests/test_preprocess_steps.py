from app.data import pipeline as dp
from types import SimpleNamespace

from app.configuration import DataSettings, PathsSettings
from app.data import pipeline as dp
from app.data.preprocess import HtmlCleaner, SimpleTokenizer


def test_cleaner_and_tokenizer(monkeypatch):
    def fake_settings():
        return SimpleNamespace(
            data=DataSettings(
                steps={
                    "clean": "app.data.preprocess.cleaning.HtmlCleaner",
                    "tokenize": "app.data.preprocess.tokenizer.SimpleTokenizer",
                }
            ),
            paths=PathsSettings(),
        )

    monkeypatch.setattr(dp, "get_settings", fake_settings)
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
