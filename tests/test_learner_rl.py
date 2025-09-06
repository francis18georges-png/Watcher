from pathlib import Path
import json

from app.core.learner import Learner
from app.core.benchmark import Bench


def test_policy_updates_with_reward(tmp_path: Path) -> None:
    bench = Bench()
    learner = Learner(bench, tmp_path)

    # Give low rewards to prompt A
    for _ in range(3):
        learner.update_policy(0.1, {"prompt": "A"})

    # Give higher rewards to prompt B
    for _ in range(3):
        learner.update_policy(1.0, {"prompt": "B"})

    policy = json.loads((tmp_path / "policy.json").read_text())
    assert policy["current_prompt"] == "B"
