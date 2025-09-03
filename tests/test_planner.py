import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.planner import Planner
import pytest


def test_briefing_includes_sections() -> None:
    plan = Planner().briefing(
        "Créer un outil",
        inputs=["spec"],
        outputs=["code"],
    )
    assert "objectif: Créer un outil" in plan
    assert "taches:" in plan
    assert "  - analyser" in plan


def test_briefing_requires_objective() -> None:
    planner = Planner()
    with pytest.raises(ValueError):
        planner.briefing("   ")

