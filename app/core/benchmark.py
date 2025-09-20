"""Utilities to simulate lightweight benchmarks and surface results."""

from __future__ import annotations

from pathlib import Path
import hashlib
import html
from typing import Final


class Bench:
    """Simple benchmark helper used by the learner and UI components.

    The implementation purposely returns deterministic pseudo random scores so
    unit tests can rely on stable values without running heavy workloads.  When
    a benchmark score is produced we also expose helpers to refresh an SVG
    badge stored in :mod:`metrics/`.  The badge mimics Shields.io output which
    means we occasionally receive colour keywords (``brightgreen`` for
    instance).  Those keywords are not valid SVG colour values so they need to
    be translated before writing the badge to disk.
    """

    _BADGE_FILE: Final[str] = "performance_badge.svg"
    _DEFAULT_BADGE_COLOR: Final[str] = "brightgreen"
    _COLOR_ALIASES: Final[dict[str, str]] = {
        # Canonical colours taken from https://shields.io/docs/colors
        "brightgreen": "#4c1",
        "success": "#4c1",
        "important": "#fe7d37",
        "critical": "#e05d44",
        "informational": "#007ec6",
        "inactive": "#9f9f9f",
    }

    def __init__(self, badge_path: Path | None = None) -> None:
        self.badge_path = (
            Path(badge_path)
            if badge_path is not None
            else Path("metrics") / self._BADGE_FILE
        )

    def run_variant(self, name: str) -> float:
        """Return a deterministic pseudo-random score for ``name``."""

        h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
        return (h % 1000) / 1000.0

    # ------------------------------------------------------------------
    # Badge helpers
    def _normalise_color(self, color: str) -> str:
        """Translate Shields.io colour keywords into valid SVG colours."""

        colour = color.strip()
        if not colour:
            return colour
        if colour.startswith("#"):
            return colour
        return self._COLOR_ALIASES.get(colour.lower(), colour)

    def _update_badge(
        self,
        value: float | str,
        *,
        label: str = "performance",
        color: str = _DEFAULT_BADGE_COLOR,
        fmt: str = "{:.0%}",
    ) -> Path:
        """Render and persist the badge representing ``value``.

        Parameters
        ----------
        value:
            Numerical score (0.0 – 1.0) or pre-formatted string shown on the
            badge.
        label:
            Text shown on the left side of the badge.
        color:
            Shields colour keyword or any valid SVG colour.
        fmt:
            Format string used when ``value`` is numeric.
        """

        if isinstance(value, str):
            right_text = value
        else:
            numeric = max(0.0, min(1.0, float(value)))
            try:
                right_text = fmt.format(numeric)
            except Exception:  # pragma: no cover - defensive fallback
                right_text = f"{numeric:.0%}"

        svg = self._render_svg_badge(label, right_text, color)
        self.badge_path.parent.mkdir(parents=True, exist_ok=True)
        self.badge_path.write_text(svg, encoding="utf-8")
        return self.badge_path

    def _render_svg_badge(self, label: str, message: str, color: str) -> str:
        """Create a tiny SVG badge similar to Shields.io output."""

        colour = self._normalise_color(color)
        safe_label = html.escape(label.strip())
        safe_message = html.escape(message.strip())

        def _text_width(text: str) -> int:
            # Roughly estimate the width used by the text using a monospace font
            # approximation (Shields uses a similar heuristic).  Enforce a
            # minimum width so very short texts still look balanced.
            return max(40, len(text) * 7 + 20)

        left_width = _text_width(safe_label)
        right_width = _text_width(safe_message)
        total_width = left_width + right_width
        label_x = left_width // 2
        value_x = left_width + right_width // 2

        return (
            "<svg xmlns=\"http://www.w3.org/2000/svg\" "
            f"width=\"{total_width}\" height=\"20\" role=\"img\" "
            f"aria-label=\"{safe_label}: {safe_message}\">\n"
            f"  <title>{safe_label}: {safe_message}</title>\n"
            f"  <rect width=\"{left_width}\" height=\"20\" fill=\"#555\"/>\n"
            f"  <rect x=\"{left_width}\" width=\"{right_width}\" height=\"20\" "
            f"fill=\"{colour}\"/>\n"
            "  <g fill=\"#fff\" text-anchor=\"middle\" "
            "font-family=\"Verdana,Geneva,DejaVu Sans,sans-serif\" "
            "font-size=\"11\">\n"
            f"    <text x=\"{label_x}\" y=\"14\">{safe_label}</text>\n"
            f"    <text x=\"{value_x}\" y=\"14\">{safe_message}</text>\n"
            "  </g>\n"
            "</svg>\n"
        )
