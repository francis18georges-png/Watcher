"""Text cleaning helpers.

The :class:`HtmlCleaner` class removes basic HTML markup and normalises
whitespace. It implements the :class:`~app.data.pipeline.PipelineStep`
protocol, making it suitable for use in :func:`app.data.pipeline.run_pipeline`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class HtmlCleaner:
    """Strip HTML tags and collapse whitespace in text."""

    def __call__(self, data: Any) -> str:
        """Return *data* with HTML tags removed.

        Parameters
        ----------
        data:
            Text to clean. Non-string inputs are converted to ``str``.
        """

        text = str(data)
        logger.debug("cleaning text of length %d", len(text))
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse repeated whitespace
        text = re.sub(r"\s+", " ", text).strip()
        logger.debug("cleaned text -> %s", text)
        return text
