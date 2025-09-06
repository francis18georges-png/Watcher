from app.data import pipeline as dp


class AddA:
    def __call__(self, data):
        data.append("a")
        return data


class AddB:
    def __call__(self, data):
        data.append("b")
        return data


def fake_config(section=None):
    if section == "data":
        return {
            "steps": {
                "first": "tests.test_pipeline_extensible.AddA",
                "second": "tests.test_pipeline_extensible.AddB",
            }
        }
    return {}


def test_pipeline_extensible(monkeypatch):
    monkeypatch.setattr(dp, "load_config", fake_config)
    result = dp.run_pipeline([])
    assert result == ["a", "b"]
