from types import SimpleNamespace

from app.configuration import DataSettings, PathsSettings
from app.data import pipeline as dp


class AddA:
    def __call__(self, data):
        data.append("a")
        return data


class AddB:
    def __call__(self, data):
        data.append("b")
        return data


def test_pipeline_extensible(monkeypatch):
    def fake_settings():
        return SimpleNamespace(
            data=DataSettings(
                steps={
                    "first": "tests.test_pipeline_extensible.AddA",
                    "second": "tests.test_pipeline_extensible.AddB",
                }
            ),
            paths=PathsSettings(),
        )

    monkeypatch.setattr(dp, "get_settings", fake_settings)
    result = dp.run_pipeline([])
    assert result == ["a", "b"]
