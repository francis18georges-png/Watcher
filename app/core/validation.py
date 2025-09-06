from typing import Any


def validate_prompt(prompt: Any) -> str:
    """Validate that the given prompt is a non-empty string.

    Parameters
    ----------
    prompt: Any
        The user provided prompt to validate.

    Returns
    -------
    str
        The original prompt if it is valid.

    Raises
    ------
    TypeError
        If *prompt* is not an instance of :class:`str`.
    ValueError
        If the prompt is empty or consists solely of whitespace.
    """
    if not isinstance(prompt, str):
        raise TypeError("Prompt must be a string")
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    return prompt
