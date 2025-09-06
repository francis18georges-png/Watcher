"""Tokenisation utilities."""

from __future__ import annotations

import logging
import re
from typing import Any, List

logger = logging.getLogger(__name__)


class SimpleTokenizer:
    """Split text into lowercase word tokens."""

    def __call__(self, data: Any) -> List[str]:
        """Tokenise *data* and return a list of words.

        Parameters
        ----------
        data:
            Text to tokenise. Non-string inputs are converted to ``str``.
        """

        text = str(data)
        logger.debug("tokenising text of length %d", len(text))
        tokens = re.findall(r"\w+", text.lower())
        logger.debug("generated %d tokens", len(tokens))
        return tokens
