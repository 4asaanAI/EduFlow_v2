---
title: AI Layer Orchestration Hardening
date: 2026-05-13
status: done
epic: Tool Orchestration Reliability
---

# AI Layer Orchestration Hardening

## Story

As an Eduflow user, I want the AI assistant to safely understand tool requests and write actions, so that it behaves like a reliable school operations assistant rather than exposing raw model JSON or asking me to confirm incomplete actions.

## Acceptance Criteria

1. Given the model emits a normal action JSON object, when the backend parses the response, then it extracts the tool name, parameters, and reason.
2. Given the model emits a confirmation JSON object, when the backend parses the response, then it maps the object to the existing confirmation-token flow.
3. Given a write action is missing required parameters, when the backend prepares confirmation, then it asks for the missing fields.
4. Given a tool result contains high-risk personal information, when it is persisted in chat traces or sent to the model for response synthesis, then the sensitive values are redacted or masked.
5. Given an HOD user has `hod` or `HOD` as sub-category, when school context is built, then HOD-specific context is returned.

## Implementation Notes

- Parser changes are centralized in `backend/routes/chat.py`.
- Write action requirements are declared with `WRITE_TOOL_REQUIRED_PARAMS`.
- Redaction is applied with `_safe_tool_result_for_chat` before tool traces are persisted or reused in final model narration.
- HOD casing support is handled in `backend/ai/context_builder.py`.

## Verification

```bash
python3 -m pytest tests/backend/unit/test_chat_confirm_gate_phase5.py
python3 -m compileall backend/ai backend/routes/chat.py
```

Result: passed.

