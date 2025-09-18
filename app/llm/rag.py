"""Minimal RAG pipeline skeleton.

- retrieve top passages from vector store
- call an LLM (placeholder) with context + prompt
"""

from __future__ import annotations
import logging
from typing import List

from app.embeddings.store import SimpleVectorStore

logger = logging.getLogger(__name__)


def build_prompt(question: str, passages: List[str]) -> str:
    context = "\n\n".join(
        f"PASSAGE {i + 1}:\n{content}" for i, content in enumerate(passages)
    )
    return (
        f"Contexte:\n{context}\n\nQuestion: {question}\n"
        "Réponds en t'expliquant si tu utilises les passages."
    )


def fake_llm(prompt: str) -> str:
    return "RÉPONSE_SIMULÉE: " + prompt[:300]


def answer_question(question: str, k: int = 3):
    vs = SimpleVectorStore()
    hits = vs.search(question, k=k)
    passages = [item[0].get("text", "") for item in hits] if hits else []
    prompt = build_prompt(question, passages)
    logger.debug("Prompt length %d", len(prompt))
    return fake_llm(prompt)
