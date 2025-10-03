"""RAG helper relying on the local vector store and llama.cpp."""

from __future__ import annotations

import logging
from typing import Sequence

from app.embeddings.store import SimpleVectorStore
from app.llm.client import Client

logger = logging.getLogger(__name__)


def build_prompt(question: str, passages: Sequence[str]) -> str:
    context = "\n\n".join(
        f"PASSAGE {i + 1}:\n{content}" for i, content in enumerate(passages) if content
    )
    header = "Contexte:\n" + context if context else "Contexte: (aucun)"
    return (
        f"{header}\n\nQuestion: {question}\n"
        "Réponds en expliquant brièvement quelles sources tu utilises."
    )


def answer_question(
    question: str,
    k: int = 3,
    *,
    client: Client | None = None,
    store: SimpleVectorStore | None = None,
) -> str:
    vector_store = store or SimpleVectorStore()
    hits = vector_store.search(question, k=k)
    passages = [item[0].get("text", "") for item in hits if item[0].get("text")]
    prompt = build_prompt(question, passages)
    logger.debug("Prompt length %d", len(prompt))
    llm = client or Client()
    answer, _ = llm.generate(prompt, separator="\n")
    return answer
