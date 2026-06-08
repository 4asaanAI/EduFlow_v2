"""Optional ChromaDB + fastembed vector index for memory recall.

Cloned/adapted from Odysseus `src/memory_vector.py`. Per the **G.1 infra spike**
(see `_bmad-output/implementation-artifacts/ai-hardening/story-G.1-spike.md`), the
vector path is **OFF by default** and gated behind `MEMORY_VECTOR_ENABLED=true`:
chromadb + fastembed pull `onnxruntime` (~200 MB) and download an embedding model on
cold start, which is risky on small Elastic Beanstalk instances. EduFlow therefore
ships **keyword-first** (always available, zero deps) and treats vectors as an
opt-in enhancement that must **degrade gracefully** (FR33).

`get_memory_vector_store()` returns a singleton whose `.healthy` is False whenever
the deps/flag are absent — callers (the store's hybrid recall) then fall back to
keyword scoring. Nothing in this module may raise to the caller.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# fastembed default — small, CPU-friendly, multilingual-ish; chosen in the G.1 spike.
_EMBED_MODEL = os.environ.get("MEMORY_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
_COLLECTION = "eduflow_ai_memories"


def vector_enabled() -> bool:
    return os.environ.get("MEMORY_VECTOR_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class MemoryVectorStore:
    """Thin wrapper over a Chroma collection; never raises to the caller."""

    def __init__(self):
        self._model = None
        self._collection = None
        self._healthy = False
        if vector_enabled():
            self._initialize()
        else:
            logger.info("MemoryVectorStore disabled (MEMORY_VECTOR_ENABLED is off)")

    def _initialize(self) -> None:
        try:
            import chromadb  # type: ignore
            from fastembed import TextEmbedding  # type: ignore

            self._model = TextEmbedding(model_name=_EMBED_MODEL)
            client = chromadb.Client()
            self._collection = client.get_or_create_collection(
                name=_COLLECTION, metadata={"hnsw:space": "cosine"}
            )
            self._healthy = True
            logger.info("MemoryVectorStore ready (model=%s)", _EMBED_MODEL)
        except Exception as e:  # missing deps, model download failure, etc.
            self._healthy = False
            logger.warning("MemoryVectorStore unavailable, falling back to keyword: %s", e)

    @property
    def healthy(self) -> bool:
        return self._healthy

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return [list(v) for v in self._model.embed(texts)]

    def _doc_id(self, school_id: str, user_id: str, memory_id: str) -> str:
        return f"{school_id}:{user_id}:{memory_id}"

    def add(self, *, school_id: str, user_id: str, memory_id: str, text: str) -> None:
        if not self._healthy or not text:
            return
        try:
            did = self._doc_id(school_id, user_id, memory_id)
            self._collection.upsert(
                ids=[did],
                embeddings=self._embed([text]),
                documents=[text],
                metadatas=[{"school_id": school_id, "user_id": user_id, "memory_id": memory_id}],
            )
        except Exception as e:
            logger.warning("vector add failed (%s): %s", memory_id, e)

    def remove(self, *, school_id: str, user_id: str, memory_id: str) -> None:
        if not self._healthy:
            return
        try:
            self._collection.delete(ids=[self._doc_id(school_id, user_id, memory_id)])
        except Exception as e:
            logger.warning("vector remove failed (%s): %s", memory_id, e)

    def search(self, *, school_id: str, user_id: str, query: str, k: int = 8) -> List[Dict]:
        """Return [{memory_id, score}] for this (school, user) scope, best-first.

        Tenant isolation (FR34): the `where` filter pins school_id AND user_id, so
        one owner's vectors can never surface for another.
        """
        if not self._healthy or not query:
            return []
        try:
            res = self._collection.query(
                query_embeddings=self._embed([query]),
                n_results=k,
                where={"$and": [{"school_id": school_id}, {"user_id": user_id}]},
            )
            ids = (res.get("ids") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            out = []
            for i, _did in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                dist = dists[i] if i < len(dists) else 1.0
                out.append({"memory_id": meta.get("memory_id"), "score": round(1.0 - dist, 4)})
            return [o for o in out if o["memory_id"]]
        except Exception as e:
            logger.warning("vector search failed: %s", e)
            return []


_singleton: Optional[MemoryVectorStore] = None


def get_memory_vector_store() -> MemoryVectorStore:
    global _singleton
    if _singleton is None:
        _singleton = MemoryVectorStore()
    return _singleton


def reset_memory_vector_store() -> None:
    """Test hook — drop the singleton so a flag change is re-read."""
    global _singleton
    _singleton = None
