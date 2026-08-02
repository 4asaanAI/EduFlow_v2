# AI Provider: Groq Primary + Azure Fallback

## How it works

Every chat turn (tool calls, follow-ups, streaming final answers) goes through a
two-provider chain:

1. **Groq** (`openai/gpt-oss-120b`, `https://api.groq.com/openai/v1`) — **primary**
2. **Azure OpenAI** (`gpt-5.3-chat`) — **automatic fallback**

If Groq succeeds, Azure is never called. If Groq fails for any reason (network
error, rate limit, 4xx/5xx, timeout), the system automatically retries with Azure
and the user receives a normal response. The failure is always logged as a WARNING
— no silent failures.

For streaming responses: fallback only happens if Groq errors *before* any text
has been sent to the client. If Groq has already started streaming, we cannot
switch mid-stream; the error is forwarded as-is (existing error handling in the
SSE layer takes over).

## Debug console logs

Two `print()` statements in `backend/ai/llm_client.py` tell you which provider is
active at runtime:

```
groq       ← Groq handled the turn
existing   ← Azure handled the turn (Groq absent or failed)
```

Remove these once you are satisfied Groq is working correctly in production.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Optional | Groq API key. If absent, Groq is skipped and Azure is used directly. |
| `AZURE_OPENAI_API_KEY` | Required (non-dev) | Azure OpenAI key (also accepts `AZURE_OPENAI_KEY`). |
| `AZURE_OPENAI_ENDPOINT` | Required (non-dev) | Azure OpenAI endpoint URL. |
| `AZURE_OPENAI_DEPLOYMENT` | Optional | Azure deployment name (default: `gpt-5.3-chat`). |

## Local dev setup

Add to `backend/.env`:
```
GROQ_API_KEY=gsk_...your_key_here...
```

## Production (AWS Elastic Beanstalk)

Set `GROQ_API_KEY` in the Elastic Beanstalk environment variables under
**Configuration → Software → Environment properties**.

## Where the logic lives

All provider logic is in `backend/ai/llm_client.py`:

- `LLMClient.__init__` — builds both clients from env vars
- `LLMClient._attempt_chat()` — single provider attempt with retry + span
- `LLMClient.chat()` — orchestrates Groq → Azure for non-streaming turns
- `LLMClient.chat_stream()` — orchestrates Groq → Azure for streaming turns

`backend/routes/chat.py` calls `llm_client.chat()` and `llm_client.chat_stream()`.

---

## Role-based tool filtering

Each chat turn sends only the tools the caller's role is authorized to use,
not all 58. The authoritative mapping lives in `backend/ai/tool_role_config.py`:

| Role | Tools sent | Schema tokens (slim) | Status |
|---|---|---|---|
| `owner` | 107 | ~11,000 | ⚠️ over 8k limit — tune EXCLUDE_FOR_ROLE |
| `admin` (principal) | 84 | ~8,700 | ⚠️ over 8k limit — tune EXCLUDE_FOR_ROLE |
| `admin` (accountant) | 62 | ~6,300 | ✓ within limit |
| `teacher` | 21 | ~2,000 | ✓ well within limit |
| `student` | 11 | ~700 | ✓ well within limit |
| `parent` | 0 | — | no parent tools registered yet |

**For owner and principal**, use `EXCLUDE_FOR_ROLE` to remove tools that are
accessed via UI flows rather than natural-language chat. Candidates that are
rarely requested through chat: `year_end_transition`, `delete_branch`,
`create_branch`, `update_branch`, `update_school_settings`. Add any others
you confirm are UI-panel-only. The token WARNING log (see below) shows the
exact count before each call so you can track progress.

To hide a tool from a role's LLM payload without removing it from the registry,
add it to `EXCLUDE_FOR_ROLE` in `tool_role_config.py`:

```python
EXCLUDE_FOR_ROLE["owner"] = {"year_end_transition", "delete_branch", "create_branch"}
```

To add a new tool with the correct role tags:
1. Add the tool to `TOOL_REGISTRY` in `tool_functions_v2.py` with `"roles": [...]`
2. It appears automatically in the correct role's LLM tool list
3. If you want to suppress it for a specific role, add it to `EXCLUDE_FOR_ROLE`

## History capping

Conversation history is capped at **2 oldest anchors + 6 most recent messages**
(constants `HISTORY_KEEP_FIRST=2`, `HISTORY_KEEP_RECENT=6` in `routes/chat.py`).
A secondary `CHAR_BUDGET=10000` char trim drops additional messages if the
total is still too large.

## Schema slim mode

`openai_tool_schema()` in `tool_functions_v2.py` defaults to `slim=True`, which
truncates tool descriptions to 80 chars and parameter descriptions to 50 chars
before serialising to JSON. Full descriptions stay in `TOOL_REGISTRY` as the
source of truth.

## Token count safeguard

Before every LLM call, `llm_client._attempt_chat()` estimates the total payload
in tokens (chars ÷ 4) and logs a WARNING if the estimate exceeds 7,000:

```
WARNING LLM payload token estimate 8412 > 7000 | provider=groq | session=... | messages=8 | tools=45
```

If you see this for a specific role, add high-token tools to `EXCLUDE_FOR_ROLE`
for that role, or upgrade the Groq plan tier.
