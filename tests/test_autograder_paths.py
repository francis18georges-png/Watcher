from contextlib import ExitStack

from app.core import autograder


def test_list_tasks_default():
    tasks = {p.name for p in autograder.list_tasks()}
    assert {"fib", "fizzbuzz", "is_prime"}.issubset(tasks)


def test_custom_dataset_path(monkeypatch, tmp_path):
    custom = tmp_path / "custom"
    # create tasks
    for name in ["alpha", "beta"]:
        tests_dir = custom / name / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / f"test_{name}.py").write_text("def test_ok():\n    assert True\n")

    monkeypatch.setenv("WATCHER_DATASETS", str(custom))

    tasks = {p.name for p in autograder.list_tasks()}
    assert tasks == {"alpha", "beta"}

    result = autograder.grade_task("alpha")
    assert result["ok"]


def test_datasets_path_env(monkeypatch, tmp_path):
    custom = tmp_path / "ds"
    monkeypatch.setenv("WATCHER_DATASETS", str(custom))

    def fail_files(_):  # resources.files should not be called
        raise AssertionError("files called")

    monkeypatch.setattr(autograder.resources, "files", fail_files)

    path = autograder._datasets_path()
    assert path == custom


def test_datasets_path_importlib(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCHER_DATASETS", raising=False)
    called = {}

    def fake_files(name: str):
        assert name == "datasets"
        return tmp_path

    class DummyCtx:
        def __enter__(self):
            called["as_file"] = True
            return tmp_path

        def __exit__(self, *exc):
            pass

    monkeypatch.setattr(autograder.resources, "files", fake_files)
    monkeypatch.setattr(autograder.resources, "as_file", lambda obj: DummyCtx())
    monkeypatch.setattr(autograder, "_DATASETS", None)
    monkeypatch.setattr(autograder, "_STACK", ExitStack())
    (tmp_path / "python").mkdir()
    path = autograder._datasets_path()
    assert called.get("as_file")
    assert path == tmp_path / "python"


def test_datasets_path_resolution(monkeypatch, tmp_path):
    """Ensure _datasets_path uses env var when set and defaults otherwise."""
    custom = tmp_path / "custom"
    monkeypatch.setenv("WATCHER_DATASETS", str(custom))
    monkeypatch.setattr(autograder, "_DATASETS", None)
    monkeypatch.setattr(autograder, "_STACK", ExitStack())
    assert autograder._datasets_path() == custom

    monkeypatch.delenv("WATCHER_DATASETS", raising=False)
    monkeypatch.setattr(autograder, "_DATASETS", None)
    monkeypatch.setattr(autograder, "_STACK", ExitStack())
    path = autograder._datasets_path()
    assert path.name == "python"
    assert path.parent.name == "datasets"
