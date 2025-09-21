"""Property-based tests for :mod:`app.core.planner`."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from hypothesis import given, settings, strategies as st

from app.core.planner import Planner


PRINTABLE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters=["\n"]),
    min_size=1,
    max_size=40,
)

OPTIONAL_SECTION = st.one_of(
    st.none(),
    st.lists(PRINTABLE_TEXT, max_size=4),
    st.lists(PRINTABLE_TEXT, max_size=4).map(tuple),
)


def _expected_section_lines(section: str, values: Iterable[str] | None) -> list[str]:
    sequence = list(values) if values is not None else []
    if not sequence:
        return [f"{section}: []"]
    lines = [f"{section}:"]
    lines.extend(f"  - {value}" for value in sequence)
    return lines


@given(
    objective=PRINTABLE_TEXT.filter(lambda s: s.strip()),
    inputs=OPTIONAL_SECTION,
    outputs=OPTIONAL_SECTION,
    constraints=OPTIONAL_SECTION,
    deliverables=OPTIONAL_SECTION,
    success=OPTIONAL_SECTION,
    platform=PRINTABLE_TEXT,
    license_name=PRINTABLE_TEXT,
)
@settings(max_examples=50, deadline=None)
def test_briefing_structure(
    objective: str,
    inputs: Iterable[str] | None,
    outputs: Iterable[str] | None,
    constraints: Iterable[str] | None,
    deliverables: Iterable[str] | None,
    success: Iterable[str] | None,
    platform: str,
    license_name: str,
) -> None:
    """Generated briefings preserve the expected ordering and content."""

    planner = Planner()
    result = planner.briefing(
        objective,
        inputs=inputs,
        outputs=outputs,
        platform=platform,
        constraints=constraints,
        license_name=license_name,
        deliverables=deliverables,
        success=success,
    )

    lines = result.splitlines()

    expected_lines: list[str] = [f"objectif: {objective}"]
    expected_lines += _expected_section_lines("entrees", inputs)
    expected_lines += _expected_section_lines("sorties", outputs)
    expected_lines.append("taches:")
    expected_lines.extend(["  - analyser", "  - implementer", "  - tester"])
    expected_lines.append(f"plateforme: {platform}")
    expected_lines += _expected_section_lines("contraintes", constraints)
    expected_lines.append(f"licence: {license_name}")
    expected_lines += _expected_section_lines("livrables", deliverables)
    expected_lines += _expected_section_lines("critere_succes", success)

    assert lines == expected_lines


@given(st.text())
@settings(max_examples=20, deadline=None)
def test_briefing_rejects_blank_objectives(objective: str) -> None:
    """Blank objectives should trigger a validation error."""

    planner = Planner()

    if objective.strip():
        planner.briefing(objective)
    else:
        with pytest.raises(ValueError):
            planner.briefing(objective)
