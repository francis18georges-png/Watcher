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

