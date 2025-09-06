"""User input validation helpers."""

from __future__ import annotations

import re
from typing import Any


# Simple list of patterns considered dangerous.  The goal is not to be
# exhaustive but to catch obviously malicious inputs such as attempts to run
# shell commands or embed scripts.  The check is performed case-insensitively.
_DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",  # destructive file removal
    r"<\s*script",  # HTML/JS injection
    r"shutdown",  # system shutdown
    r"reboot",  # system reboot
    r"sudo",  # privileged command execution
]


def validate_prompt(prompt: Any) -> str:
    """Validate that *prompt* is a safe, non-empty string.

    Parameters
    ----------
    prompt:
        The user provided prompt to validate.

    Returns
    -------
    str
        Sanitised prompt.

    Raises
    ------
    TypeError
        If *prompt* is not an instance of :class:`str`.
    ValueError
        If the prompt is empty or contains dangerous content.
    """

    if not isinstance(prompt, str):
        raise TypeError("Prompt must be a string")

    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty")

    lowered = prompt.lower()
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, lowered):
            raise ValueError("Prompt contains potentially dangerous content")

    return prompt
