"""LLM client capable of running fully offline via ``llama.cpp``."""

from __future__ import annotations

import os
import http.client
import json
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse

from config import get_settings


try:  # pragma: no cover - optional dependency
    from llama_cpp import Llama  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore[assignment]


def validate_prompt(prompt: str) -> str:
    """Return a sanitized version of *prompt*.

    Leading and trailing whitespace is stripped and an empty prompt raises a
    ``ValueError``.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    return prompt


def generate_ollama(prompt: str, *, host: str, model: str) -> str:
    """Send *prompt* to an Ollama server.

    Args:
        prompt: Text prompt to send for generation.
        host: Hostname (and optional port) of the Ollama server.
        model: Model identifier used for the request.

    The response value is returned as a stripped string.
    """

    parsed = urlparse(host if "://" in host else f"http://{host}")
    scheme = parsed.scheme or "http"
    if scheme == "https":
        connection_cls = http.client.HTTPSConnection
        default_port = 443
    else:
        connection_cls = http.client.HTTPConnection
        default_port = 11434

    conn = connection_cls(
        parsed.hostname or "127.0.0.1", parsed.port or default_port, timeout=30
    )
    try:  # pragma: no cover - network path
        payload = json.dumps({"model": model, "prompt": prompt})
        conn.request(
            "POST",
            "/api/generate",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"Generate request failed: {resp.status}")
        data = json.loads(resp.read())
        return data.get("response", "").strip()
    finally:
        try:
            conn.close()
        except Exception:  # pragma: no cover - defensive
            pass


def chunk_prompt(prompt: str, *, size: int = 1000) -> list[str]:
    """Yield slices of *prompt* of at most *size* characters."""
    if size <= 0:
        raise ValueError("size must be a positive integer")
    return [prompt[i : i + size] for i in range(0, len(prompt), size)]


class Client:
    """Generate text using an LLM backend.

    A locally running Ollama server is preferred. If it cannot be reached a
    deterministic echo response is returned so the rest of the application can
    continue to function in offline mode.

    Args:
        model: Model identifier passed to the Ollama server. If omitted, the
            value is read from ``config/settings.toml``.
        host: Hostname (and optional port) of the Ollama server. If omitted,
            the value is read from ``config/settings.toml``.
        ctx: Context window size used by the LLM. Defaults to ``None`` which
            means the value is read from ``config/settings.toml``. Must be a
            positive integer.
        fallback_phrase: Text prefix used when generation fails. When omitted
            the value defined in the configuration is used.
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        *,
        ctx: int | None = None,
        fallback_phrase: str | None = None,
    ) -> None:
        settings = get_settings()
        llm_cfg = settings.llm

        if ctx is not None and ctx < 1:
            raise ValueError("ctx must be a positive integer")

        backend = llm_cfg.backend.strip().lower()
        llm_model = model or llm_cfg.model

        # ``model`` previously referred to the remote identifier. We still honour
        # this usage by switching to the Ollama backend if the provided value
        # resembles an Ollama reference.
        if "://" in llm_model or (
            ":" in llm_model and not any(sep in llm_model for sep in ("/", "\\"))
        ):
            backend = "ollama"

        if backend in {"llama.cpp", "llama-cpp", "llamacpp"}:
            backend = "llama.cpp"
        elif backend != "ollama":
            raise ValueError(f"Unsupported LLM backend: {backend}")

        self.backend = backend
        self.model = llm_model
        self.host = host or llm_cfg.host
        self.ctx = ctx if ctx is not None else llm_cfg.ctx
        self.fallback_phrase = fallback_phrase or llm_cfg.fallback_phrase
        self.temperature = float(llm_cfg.temperature)
        self.max_tokens = int(llm_cfg.max_tokens)
        self.system_prompt = llm_cfg.system_prompt
        self.model_path = (
            settings.paths.resolve(llm_cfg.model_path)
            if backend == "llama.cpp"
            else llm_cfg.model_path
        )
        threads = llm_cfg.threads
        self.threads = (
            threads
            if threads is not None
            else max(1, os.cpu_count() or 1)
        )
        self._offline = False
        self._llama_lock = threading.RLock()
        self._llama_model: Llama | None = None

    def set_offline(self, offline: bool) -> None:
        """Enable or disable offline mode for the client."""

        self._offline = bool(offline)

    def generate(self, prompt: str, *, separator: str = "") -> tuple[str, str]:
        """Return a response and trace for *prompt*.

        Args:
            prompt: Text prompt to send for generation.
            separator: String inserted between responses for each chunk when
                concatenated. Defaults to ``""``.

        The prompt is sent in fixed-size chunks so very large prompts can be
        handled without overwhelming the backend. Successful responses from
        each chunk are concatenated before being returned.
        """

        trace: list[str] = []
        backend = getattr(self, "backend", "ollama")
        if self._offline and backend != "llama.cpp":
            trace.extend(["offline", "fallback"])
            return f"{self.fallback_phrase}: {prompt}", " -> ".join(trace)

        try:  # pragma: no cover - network path
            if backend == "llama.cpp":
                response = self._generate_llama_cpp(prompt, separator, trace)
            else:
                response = self._generate_ollama(prompt, separator, trace)
            trace.append("success")
            return response, " -> ".join(trace)
        except Exception as exc:
            trace.append(f"error:{exc.__class__.__name__}")
            trace.append("fallback")
            logging.exception("Failed to generate response: %s", exc)
            return f"{self.fallback_phrase}: {prompt}", " -> ".join(trace)

    # ------------------------------------------------------------------
    # Backend specific helpers

    def _generate_ollama(
        self, prompt: str, separator: str, trace: list[str]
    ) -> str:
        responses: list[str] = []
        for idx, chunk in enumerate(chunk_prompt(prompt)):
            trace.append(f"ollama:{idx}")
            responses.append(
                generate_ollama(chunk, host=self.host, model=self.model)
            )
        return separator.join(responses)

    def _ensure_llama(self) -> Llama:
        if Llama is None:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "llama-cpp-python is required but not installed. "
                "Ajoutez 'llama-cpp-python' à vos dépendances."
            )

        model_path = Path(self.model_path)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"Le modèle llama.cpp est introuvable: {model_path}"
            )

        with self._llama_lock:
            if self._llama_model is None:
                kwargs = {
                    "model_path": str(model_path),
                    "n_ctx": int(self.ctx or 2048),
                    "n_threads": int(self.threads),
                }
                self._llama_model = Llama(**kwargs)
        return self._llama_model

    def _generate_llama_cpp(
        self, prompt: str, separator: str, trace: list[str]
    ) -> str:
        llama = self._ensure_llama()
        responses: list[str] = []
        for idx, chunk in enumerate(chunk_prompt(prompt)):
            trace.append(f"llama.cpp:{idx}")
            completion = llama.create_chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": chunk},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            choice = completion["choices"][0]["message"]["content"]
            responses.append(str(choice).strip())
        return separator.join(responses)
