# AI Golden Eval Corpus (R11.1)

The quality-regression gate for the AI layer. Three tiers:

| Tier | File | Runs where | Needs creds? |
|------|------|-----------|--------------|
| **Structural** | `test_eval_corpus_structure.py` | every CI run (default suite) | no |
| **Judge logic** | `test_eval_judge_logic.py` | every CI run (default suite) | no |
| **LLM judge** | `test_eval_llm_judge.py` (`@llm_eval`) | credentialed nightly/pre-release | **yes** |

## The corpus

`_bmad-output/test-artifacts/eval-corpus/corpus.json` — ≥40 golden conversations
covering every role/sub_category, plus the production incident, follow-ups, ambiguous
asks, denials, and Hinglish. Each entry declares its `expected_tool`,
`expected_outcome` (`answer|confirm|denial|disambiguation|chat`), `language`, `tags`,
and a `rubric` (for the judge). Edit the JSON to add cases — the structural tier
validates coherence automatically.

## Running

```bash
# Default (structural + judge-logic; no credentials):
pytest tests/backend/evals

# Credentialed quality gate (nightly / pre-release):
AZURE_OPENAI_API_KEY=... AZURE_OPENAI_ENDPOINT=... pytest -m llm_eval tests/backend/evals
```

The LLM-judge tier runs the corpus through the **real** prompt pipeline + a real LLM
judge, scores correctness/completeness/tone per rubric, and **blocks release** if any
dimension drops more than the threshold (`judge.DEFAULT_THRESHOLD`, 0.05) below the
recorded baseline in `scores-baseline.json`. The first credentialed run writes that
baseline. A turn that produces no reply (the incident class) scores zero — it can
never be silently excused.

## When to run the LLM-judge tier

Any change to `ai/prompts.py`, `ai/tool_functions*.py`, `ai/context_builder.py`,
`ai/llm_client.py`, or the chat tool-loop should trigger a credentialed eval run
before merge — see the AI-reliability execution protocol.
