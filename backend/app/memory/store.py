"""Episodic memory with retrieval (the R in the agents' RAG loop).

Each agent owns an ``EpisodicMemory``. The engine writes game events into it
(respecting information asymmetry: private events only reach their intended
recipients), and the agent retrieves the most relevant items before every
decision.

Retrieval uses TF-IDF cosine similarity implemented in pure Python. That keeps
the arena fully self-contained and deterministic; the class boundary is where
a real embedding + vector-store backend (e.g. pgvector, Qdrant) would plug in.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class MemoryItem:
    id: str
    round: int
    kind: str  # event type: speech | vote | kill | inspect | ...
    text: str
    importance: float = 1.0


@dataclass
class RetrievedMemory:
    item: MemoryItem
    score: float


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EpisodicMemory:
    def __init__(self) -> None:
        self.items: list[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        self.items.append(item)

    def __len__(self) -> int:
        return len(self.items)

    def retrieve(self, query: str, k: int = 5) -> list[RetrievedMemory]:
        if not self.items or not query.strip():
            return []

        docs = [_tokens(i.text) for i in self.items]
        query_tokens = _tokens(query)

        # document frequencies over the memory corpus
        df: dict[str, int] = {}
        for doc in docs:
            for tok in set(doc):
                df[tok] = df.get(tok, 0) + 1
        n_docs = len(docs)

        def vector(tokens: list[str]) -> dict[str, float]:
            tf: dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            return {
                tok: (count / max(1, len(tokens))) * math.log((1 + n_docs) / (1 + df.get(tok, 0)))
                for tok, count in tf.items()
            }

        q_vec = vector(query_tokens)
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scored: list[RetrievedMemory] = []
        for item, doc in zip(self.items, docs):
            d_vec = vector(doc)
            dot = sum(v * d_vec.get(tok, 0.0) for tok, v in q_vec.items())
            d_norm = math.sqrt(sum(v * v for v in d_vec.values())) or 1.0
            score = (dot / (q_norm * d_norm)) * item.importance
            if score > 0:
                scored.append(RetrievedMemory(item=item, score=score))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]
