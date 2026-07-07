---
title: Eduflow AI Layer BMAD End-to-End Pass
date: 2026-05-13
scope: AI Layer
status: implementation-pass-complete
stepsCompleted:
  - bmad-agent-analyst
  - bmad-agent-tech-writer
  - bmad-document-project
  - bmad-product-brief
  - bmad-create-prd
  - bmad-create-ux-design
  - bmad-edit-prd
  - bmad-validate-prd
  - bmad-agent-architect
  - bmad-create-architecture
  - bmad-create-epics-and-stories
  - bmad-generate-project-context
  - bmad-check-implementation-readiness
  - bmad-agent-dev
  - bmad-create-story
  - bmad-dev-story
  - bmad-code-review
  - bmad-qa-generate-e2e-tests
  - bmad-checkpoint-preview
---

# Eduflow AI Layer BMAD End-to-End Pass

## 1. Analysis

### Current System

Eduflow's AI layer is a role-scoped school operations assistant built around:

- `backend/routes/chat.py`: conversation CRUD, SSE streaming, tool routing, confirmation flow, and response persistence.
- `backend/ai/prompts.py`: role-specific system prompt, tool catalog, safety rules, and response format rules.
- `backend/ai/context_builder.py`: live school context by user role.
- `backend/ai/tool_functions.py` and `backend/ai/tool_functions_v2.py`: read/write tool registry and domain query functions.
- `frontend/src/components/ChatInterface.js`: streaming chat UI, thinking states, tool call badges, rich content, and confirmation action UI.

### Product Brief

Eduflow AI should feel like a school-specific ChatGPT for owners, principals, admins, teachers, and students: conversational, fast, safe, aware of live school data, and able to take gated actions. The target is not a general ChatGPT clone. The stronger product direction is a domain expert assistant with ChatGPT-grade conversational reliability and Eduflow-grade operational safety.

### Key Gaps Found

- Model confirmation JSON was documented in the prompt but not parsed by the server.
- Keyword-detected write actions could generate confirmation cards with empty parameters.
- Residual tool JSON could leak into visible assistant responses.
- Tool results sent back into the model could include high-risk personal fields.
- HOD context routing used a casing mismatch and could miss HOD-specific context.

## 2. Planning

### PRD Slice

Goal: strengthen the AI layer's core orchestration so write actions, tool calling, privacy, and role context behave predictably.

Acceptance criteria:

- Given the model outputs `{"confirm_action": true, "tool": "...", "params": {...}}`, when the chat route parses it, then it normalizes it into the server confirmation gate.
- Given a write action lacks required parameters, when the AI route prepares it, then the assistant asks for the missing fields instead of sending a vague confirmation.
- Given a tool returns phone, address, date of birth, password, Aadhaar, or medical fields, when the result is stored in chat traces or sent back to the model, then those fields are masked or restricted.
- Given a teacher has sub-category `hod` or `HOD`, when context is built, then HOD context is selected.
- Given the assistant response contains leftover tool JSON, when final text is prepared, then the JSON is removed before streaming to the user.

### UX Design Direction

The current chat UI already has the right building blocks: thinking process, streaming response, tool badges, rich blocks, action buttons, retry behavior, and confirmation cards. The next UX upgrades should be operational rather than decorative:

- Show missing-field prompts as compact structured forms for fee payment, attendance, leave approval, house points, and announcements.
- Display tool traces in a collapsible "data used" panel for admins and owners.
- Use role-specific quick prompts based on the user's sub-role and current page.
- Add response quality controls: retry, shorter, more detail, export, and open source panel.

## 3. Solutioning

### Architecture Decision

Tool execution remains server-owned. The model may request or propose actions, but the backend normalizes, validates, scopes, confirms, executes, redacts, persists, and streams results.

### Epics

1. Tool Orchestration Reliability
   - Normalize all model tool JSON shapes.
   - Validate required write parameters before confirmation.
   - Prevent residual tool JSON from leaking into final answers.

2. Privacy and Safety
   - Redact sensitive tool output before model narration and message trace persistence.
   - Keep write actions behind signed confirmation tokens.
   - Preserve role and scope enforcement at every execution point.

3. Context Intelligence
   - Fix sub-role context routing.
   - Add richer class, fee, staff, and incident summaries per role.
   - Introduce context budgets and retrieval scoring for large data sets.

4. ChatGPT-Grade Interaction Quality
   - Improve multi-tool planning and synthesis.
   - Add structured missing-field collection.
   - Add response controls and better rich blocks.

## 4. Implementation

Implemented in this pass:

- Robust tool JSON parsing for `action`, `confirm_action`, arrays, fenced JSON, and embedded JSON.
- Missing required parameter detection for all server-confirmed write tools.
- LLM-assisted parameter extraction for keyword-detected write actions.
- Safe tool-result redaction before model narration and chat trace storage.
- Confirmation display fixes for `mode` and `house_name` parameters.
- HOD context routing fix for lowercase and uppercase sub-category values.
- Unit tests for confirmation parsing, JSON stripping, missing parameters, and redaction.

Changed files:

- `backend/routes/chat.py`
- `backend/ai/context_builder.py`
- `tests/backend/unit/test_chat_confirm_gate_phase5.py`

## 5. Validation

Executed:

```bash
python3 -m pytest tests/backend/unit/test_chat_confirm_gate_phase5.py
python3 -m compileall backend/ai backend/routes/chat.py
```

Result:

- 8 unit tests passed.
- Python compile check passed.

Known warnings are existing framework deprecations from FastAPI/Pydantic test imports.

## 6. Remaining Backlog

To get closer to the "as good as ChatGPT for Eduflow" target, the next stories should be:

1. True multi-tool planner: execute independent read tools, aggregate all results, and synthesize one answer.
2. Structured write forms: convert missing write parameters into frontend mini-forms instead of text-only prompts.
3. Conversation memory: summarize long chats into durable school-safe memory, not just first-plus-recent trimming.
4. Retrieval layer: indexed policy docs, school documents, uploaded files, and historical records with citations.
5. Evaluation suite: golden prompts by role, tool-selection accuracy tests, privacy leak tests, and prompt injection tests.
6. Observability: per-message latency, tool timing, model token usage, policy blocks, and answer quality tags.
7. UX polish: visible data provenance, response actions, export/share, and role-aware suggested prompts.

