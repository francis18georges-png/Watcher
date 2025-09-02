import http.client
import json


class LLMClient:
    """Simple client for a local language model API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 11434, model: str = "llama3.2:3b"):
        self.host = host
        self.port = port
        self.model = model

    def generate(self, prompt: str) -> str:
        """Return a completion for the given prompt."""
        try:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
            payload = json.dumps({"model": self.model, "prompt": prompt})
            conn.request(
                "POST",
                "/api/generate",
                body=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            data = resp.read()
            if resp.status != 200:
                raise RuntimeError(f"LLM request failed: {resp.status}")
            return json.loads(data).get("response", "")
        except Exception as e:  # pragma: no cover - network
            raise RuntimeError(f"Generation request failed: {e}")
        finally:
            try:
                conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
