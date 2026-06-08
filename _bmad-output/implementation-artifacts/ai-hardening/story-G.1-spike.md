# Story G.1 — Infra feasibility spike: chromadb + fastembed on Python 3.9 / EB

**Date:** 2026-06-08 · **Verdict: GO (keyword-first hybrid; vector behind a flag, default OFF).**

## Question
Can the Odysseus vector-memory dependencies (`chromadb` + `fastembed`) deploy on
our stack — Python 3.9 on AWS Elastic Beanstalk — before we commit to them?

## Findings
| Dimension | Finding |
|---|---|
| Python 3.9 compat | `chromadb` (client) and `fastembed` both import on 3.9; no syntax blockers. |
| Dependency weight | `fastembed` pulls `onnxruntime` (~200 MB) + tokenizers; `chromadb` pulls `hnswlib`, `pydantic`-v2 stack. Total adds ~250–300 MB to the slug. |
| Cold start | First embed call downloads the model (`BAAI/bge-small-en-v1.5`, ~130 MB) to disk and warms ONNX — multi-second first-hit latency, and EB ephemeral storage re-downloads on each deploy/scale event. |
| Memory footprint | ONNX runtime + model resident set is ~300–400 MB; tight on small EB instance classes shared with the FastAPI workers. |
| Packaging risk | `onnxruntime` wheels are platform-specific; EB Amazon Linux build must match. Non-trivial but doable. |

## Decision
**GO**, but EduFlow ships **keyword-first**:
- **Default path (always on, zero new deps):** pure-Python keyword relevance scoring
  (`services/memory/retrieval.py`, cloned from Odysseus `get_relevant_memories`).
  This is the production default and requires nothing new on EB.
- **Vector path (opt-in):** `services/memory/vector.py` is gated behind
  `MEMORY_VECTOR_ENABLED=true`. When the flag/deps are absent, `MemoryVectorStore.healthy`
  is `False` and recall **degrades gracefully to keyword-only** (FR33). Chosen embedding
  model when enabled: **`BAAI/bge-small-en-v1.5`** via `fastembed` (override with
  `MEMORY_EMBED_MODEL`).

## Why this is the right call
- De-risks the deploy: no heavyweight deps reach EB unless an operator deliberately
  enables them after validating instance size.
- Hybrid recall (`store.recall`) is written so vector is *additive* — it only contributes
  extra semantic candidates and re-ranks by the deterministic keyword score, so behavior
  is never *worse* than keyword-only and is stable/testable without the model.
- Satisfies the G.1 fallback clause verbatim: "keyword-only retrieval if vectors aren't viable."

## Follow-ups (not blockers for Epic G)
- If/when vector is enabled in staging: pin `onnxruntime` wheel, bake the model into the
  AMI/slug to avoid cold-start downloads, and confirm instance RSS headroom.
