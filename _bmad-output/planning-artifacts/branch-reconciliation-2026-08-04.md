# The school is not running `main`. Reconciliation for Abhimanyu to referee.

Written 2026-08-04. **Read this before any deploy.**

## How this was found

Not by looking for it. While reading the live usage records to sort out the school owner's
exhausted AI allowance, two rows stood out:

```
'model': 'openai/gpt-oss-120b', 'provider': 'groq'   (2026-08-02 and 2026-08-03)
```

The word "groq" does not appear anywhere in `main`. The only place in this repository that
writes a provider name is `routes/chat.py`, and it writes the literal string
`"azure_openai"`. So the code that produced those rows is not the code in `main`.

It is on **`origin/local_testing`**, Shubham's branch, tip commit `28d6558` dated
**2026-08-02**, titled *"Add AI flow logging; fix Groq TPM 413/throttling; attribute tokens
to real model"*.

## What this means, stated plainly

1. **The school is running Shubham's branch.** Not `main`, and not the branch three rounds of
   inspection work were verified against.
2. **Everything verified this week is correct for `main`, and unverified for what the school
   actually runs.** That is not a claim that anything is broken. It is a claim that the
   evidence does not cover the thing it appeared to cover.
3. **Deploying `main` today would remove work the school currently depends on**, including
   the Groq throttling fix. That is the immediate risk and the reason this document exists.
4. Nobody wrote any of this down. The deploy notes, the register and the project guide all
   describe a single line of development.

## The two of us did the same job twice, independently

This is the part worth pausing on. Shubham and I each solved the same two problems, from
scratch, without knowing the other had.

| Problem | Shubham, on `local_testing` (2 Aug) | Me, on the inspection branch (4 Aug) |
|---|---|---|
| The wasteful second AI call per message | `AI_STREAM_SECOND_CALL`, **default off** | `AI_STREAM_SECOND_CALL`, **default off** |
| Too many tools sent to the model | `EXCLUDE_FOR_ROLE` in `ai/tool_role_config.py` | `EXCLUDE_FOR_ROLE` in `ai/tool_chat_exclusions.py` |

Same idea, same switch name, two different files. The register even told me his branch
"already sketches this, reuse the idea, do not merge that branch to get it" — which I
followed, and which is exactly how we ended up with two of everything.

**The duplicated effort is the cheap part. The expensive part is that neither of us knew the
school was running the other's assumption.**

## Where the two versions genuinely differ

| Area | On `local_testing` only | Judgement |
|---|---|---|
| **Groq as the primary model** | A whole second provider path in `llm_client.py`: `GROQ_BASE_URL`, `GROQ_MODEL = openai/gpt-oss-120b`, a 8,000 tokens-per-minute ceiling with a safety margin, and `reasoning_effort=low` to cut hidden spend | **His must survive.** This is live and load-bearing. |
| **Honest usage attribution** | `token_service` records the provider and model that actually answered, instead of assuming Azure | **His must survive**, and it is what made this discovery possible at all. |
| **Tool trimming** | ~35 tools excluded, **owner only**, sized to fit Groq's 8k limit | **His constraint is harder than mine.** Mine trims 26 for owner and principal on cost grounds. His is a technical ceiling: on Groq free tier, my 81-tool list would still breach 8k TPM. |
| **Second-call switch** | Same switch, same default | Identical outcome. Keep one, delete the other. |
| **Detailed flow logging** | Console and server tracing across the whole send path | Useful; no conflict with anything of mine. |
| **Prompt trimming** | `prompts.py` net **107 lines shorter** | Needs a proper look. Shrinking a prompt to fit a token ceiling can quietly change what Flo knows. |

And on my branch only: the attendance-register fix, the truncation honesty, the removal of
27 per-row query loops, the error shapes, the build gate, the repaired tests, and the real
write-rollback test run. None of that exists on his branch.

**The two sets of changes overlap in exactly four files** (`llm_client.py`, `prompts.py`,
`chat.py`, `tool_functions_v2.py`) and are otherwise disjoint.

## The question that actually needs answering first

**Is the school meant to be on Groq or on Azure?**

Everything else follows from it, and it is a decision, not a technical detail:

- The production server's settings still point at **Azure** (`Odin`, on the Layaa AI
  resource). I connected to it today and it answers.
- The live usage records show **Groq** answering on 2 and 3 August.
- Groq's free tier ceiling of 8,000 tokens per minute is what forced the aggressive tool
  trimming. My cost work (26 tools trimmed, second call off) reduces an owner's turn from
  ~43,000 tokens to ~17,000 — which is a large improvement on Azure and **still far above
  8,000 on Groq.**

So the two of us optimised against two different ceilings. Until you and Shubham settle
which provider the school is on, neither trimming list is definitively right.

## What I recommend, and I would rather be overruled than guess

1. **Do not deploy anything until this is settled.** You already decided to ship everything
   in one go, which makes this a blocker rather than an inconvenience.
2. **Put the provider question to Shubham first.** He has operational knowledge I do not: why
   Groq, whether it is temporary, whether the Azure credit position drove it.
3. **Then combine, in this order:** his provider work as the base, my correctness work on
   top, one tool-exclusion file rather than two, sized to whichever ceiling wins.
4. **Write down which branch production runs**, somewhere that is checked. The reason this
   went unnoticed for two days is that nothing anywhere states it.

## What I have NOT done

I have not merged, cherry-picked, reverted, or touched `local_testing` in any way. I have not
changed the production server's settings. Read-only throughout.
