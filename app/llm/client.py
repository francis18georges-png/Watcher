"""Simple LLM client interface for Watcher."""


class Client:
    """Minimal client returning a deterministic response.

    This is a placeholder for a real language model backend. Replace the
    implementation of :meth:`generate` with an actual model call when
    integrating a true LLM.
    """

    def generate(self, prompt: str) -> str:
        """Return a response for *prompt*.

        Parameters
        ----------
        prompt:
            Input text to send to the model.
        """
        return f"Echo: {prompt}"
