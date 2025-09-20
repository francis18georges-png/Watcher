from app.ui import main


class _DummyTree:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, str, str]] = {}

    def insert(self, _parent, _index, values):
        iid = f"item{len(self.rows)}"
        self.rows[iid] = values
        return iid

    def item(self, iid, *, values):
        self.rows[iid] = values

    def delete(self, iid):  # pragma: no cover - not exercised in test
        self.rows.pop(iid, None)


class _DummyEngine:
    offline_mode = False

    def __init__(self) -> None:
        self.client = type("Client", (), {"host": "demo", "model": "demo"})()

    def plugin_metrics(self):
        return [{"name": "hello", "cpu": 12.34, "memory": 56.78}]


def test_refresh_plugin_metrics_formats_strings():
    app = main.WatcherApp.__new__(main.WatcherApp)
    app.engine = _DummyEngine()
    app.plugin_tree = _DummyTree()
    app._plugin_rows = {}
    app.after = lambda delay, func: None
    app.offline_btn = type("Btn", (), {"config": lambda self, **kwargs: None})()
    app.status_var = type("Var", (), {"set": lambda self, value: None})()

    main.WatcherApp._refresh_plugin_metrics(app)

    assert app.plugin_tree.rows
    entry = next(iter(app.plugin_tree.rows.values()))
    assert entry[0] == "hello"
    assert entry[1].endswith("%")
    assert entry[2].endswith("MiB")
