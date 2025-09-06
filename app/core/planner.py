"""Simple planner returning a structured project brief."""

from __future__ import annotations

from typing import Iterable


class Planner:
    """Build YAML-like project specifications.

    The planner validates the provided *objective* and generates a minimal
    briefing including common sections (inputs, outputs, constraints...).
    """

    def briefing(
        self,
        objective: str,
        *,
        inputs: Iterable[str] | None = None,
        outputs: Iterable[str] | None = None,
        platform: str = "windows",
        constraints: Iterable[str] | None = None,
        license_name: str = "MIT",
        deliverables: Iterable[str] | None = None,
        success: Iterable[str] | None = None,
    ) -> str:
        """Return a YAML-formatted project brief.

        Parameters
        ----------
        objective:
            Main goal of the project. Must be non-empty.
        inputs/outputs/platform/constraints/license_name/deliverables/success:
            Optional sections used to enrich the generated brief.
        """

        if not objective.strip():
            raise ValueError("objective must be a non-empty string")

        def fmt(section: str, values: Iterable[str] | None) -> list[str]:
            if not values:
                return [f"{section}: []"]
            lines = [f"{section}:"]
            lines.extend(f"  - {v}" for v in values)
            return lines

        lines = [f"objectif: {objective}"]
        lines += fmt("entrees", inputs)
        lines += fmt("sorties", outputs)
        lines.append("taches:")
        lines.extend(f"  - {t}" for t in ["analyser", "implementer", "tester"])
        lines.append(f"plateforme: {platform}")
        lines += fmt("contraintes", constraints)
        lines.append(f"licence: {license_name}")
        lines += fmt("livrables", deliverables)
        lines += fmt("critere_succes", success)
        return "\n".join(lines)
