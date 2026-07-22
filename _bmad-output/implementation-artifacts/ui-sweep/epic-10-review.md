# Epic 10 — Quality Gate Output

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

Review lenses applied over the epic's combined diff: code review, adversarial general,
edge-case hunter, test review, AC trace, NFR, plus the scoped-query audit.

> **Honesty note on the gate.** The diff moved twice during the epic: the owner
> revised the image-access rule (teachers removed) and asked for OCR mid-build. Both
> were implemented and then re-reviewed. As in Epic 4, the gate was applied in passes
> rather than once over a frozen artefact, and that is stated rather than implied.

---

## Findings — all fixed in-run

| # | Sev | Where | Finding | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | 🔴 | `ai/tool_functions_v2.py` | **Caught by the write-classification parity gate, not by me.** The tool was registered as `generate_document` and was neither flagged a write nor allowlisted. The guard exists so a mutating tool cannot bypass confirm/kill-switch/audit behind an innocent name, and "generate_" reads as mutating. | Classified deliberately: it creates a file but changes no school record, so it stays read-class. **Renamed to `draft_document`** to match the `draft_parent_message` convention, and allowlisted with the full reasoning written into the allowlist. | `test_it_is_a_read_class_tool_and_needs_no_confirmation` |
| F-2 | 🔴 | `ai/prompts.py` | **Caught by the prompt↔registry parity gate.** The tool was authorised for owner/admin/teacher but advertised in no prompt — users could never reach it through Flo. Exactly the drift class epic R3 exists to prevent. | Advertised in all four matching role lists, with an instruction to always append the `file` block after using it. | the parity gate itself |
| F-3 | 🟠 | `routes/chat_upload.py` | The endpoint resolved a db handle for the new audit write but was not wired into the test harness, so auditing silently failed. | `chat_upload.get_db` patched in `conftest.py`. | `test_reading_an_image_is_audited` |
| F-4 | 🟠 | `services/document_export.py` | Same: the service resolves its own db handle and 500'd inside the tool. | `document_export.get_db` patched in `conftest.py`. | the whole file |
| F-5 | 🟠 | `MessageRenderer.js` | Rich blocks are **authored by the model**, so `download_url` is untrusted. A `javascript:` or `data:` URL would have become a click target. | Only `http(s)` is made clickable; anything else renders as the expired state. | 4 parametrised cases |
| F-6 | 🟠 | `services/document_builder.py` | Excel silently refuses to open a workbook whose sheet name contains `[]:*?/\` or exceeds 31 chars — it does not warn. A title like "Fees [2026]: Class 5/A?" would have produced an unopenable file. | Sheet names sanitised and truncated. | `test_an_excel_sheet_name_cannot_break_the_workbook` |
| F-7 | 🟠 | `services/document_builder.py` | fpdf2's core fonts are Latin-1. A Hindi circular would have **raised and lost the whole document**. | Transliterated rather than crashing, and pinned as a known limit rather than hidden. | `test_devanagari_does_not_lose_the_whole_pdf` |
| F-8 | 🟡 | `routes/exports.py` | `export_expenses` uses `scoped_filter` while every neighbouring export uses `scoped_query(branch_id=...)`. | **Annotated, not changed** — narrowing it alters what an accountant sees, which is a permission decision this story does not own. Logged as D-29. | audit |

## Findings dismissed, with reasons

| Finding | Why dismissed |
|---|---|
| "Document generation should require a confirm step like other AI actions" | Considered and rejected explicitly. It changes no school record, so there is nothing to undo; the kill-switch guards AI *writes to school data*, not the production of a file. Its real controls are the role gate, the audit row and the shared daily cap. Recorded in the allowlist comment and pinned by a test so it is not silently "fixed" later. |
| "OCR should also run on PDFs" | A scanned PDF genuinely needs it, and `pypdf` already returns "no extractable text found (may be scanned)" for those. Rasterising PDF pages needs `pdf2image` + poppler, another system binary. Out of scope; logged as D-30. |
| "The vision fallback should be a tool Flo can call on demand" | It would be better — Flo has the conversation and knows whether the person asked what a picture *says* or what it *shows*. But the image bytes live at the upload boundary, not in the tool loop. Wiring that is real work; the upload-time fallback satisfies the AC honestly. Logged as D-31. |
| Devanagari in PDFs | Needs an embedded Unicode font (e.g. Noto Sans Devanagari) shipped with the app. Worth doing when a Hindi circular is genuinely needed as a PDF; the limit is pinned by a test rather than left to be rediscovered. |

## Scoped-filter / scoped-query audit — every touched backend file

| File | Hits | Verdict |
|---|---|---|
| `services/document_builder.py`, `document_export.py`, `ocr_service.py`, `vision_service.py` | 0 | no direct DB reads of operational collections |
| `routes/exports.py` | 1 | **annotated** (F-8 / D-29); pre-existing |
| `routes/chat_upload.py` | 0 | |
| `ai/tool_functions_v2.py` | 2 | pre-existing attendance filters, untouched by this epic |
| `ai/prompts.py` | 0 | |

**No new `scoped_filter` call was introduced by this epic.**

## NFR check

| NFR | Result |
|---|---|
| NFR-S1 | No permission widened. 14 tests assert the export gates are exactly as before. |
| NFR-S2 | Audit rows carry ids, counts and sizes — never document content or extracted text. Two tests assert a name, a phone number and a medical word are absent. |
| NFR-A2 / UX-DR9 | The file card carries `data-testid`, is a real link (keyboard reachable), and states its type in text rather than by colour. |
| Error opacity (P3) | The vision service never returns exception text to the caller. |
| Tenancy | Generated files are keyed under `{school_id}/uploads/...` and the `file_uploads` record is school-scoped. Asserted. |
| Cost | Daily cap shared with certificates; the paid vision path is a fallback only, asserted not to run when OCR succeeded. |

## AC trace

Every AC on Stories 10.1–10.6 maps to at least one test, except three that cannot be
asserted here and are named on the human checklist as **not verified by this run**:

1. That a generated `.docx`/`.xlsx`/`.pptx` opens correctly in **Microsoft Office**.
   The tests parse them with the same libraries that wrote them, which proves the file
   is structurally valid but not that Word is happy with it.
2. That **Tesseract actually reads a photograph of a real fee slip** — the binary is
   not installed, so every test exercises the "unavailable" path or a fake.
3. That the **deployed chat model accepts images** at all. Unknown until tried.

## Final counts

| | Result |
|---|---|
| Backend | **1915 passed, 2 failed (pinned D-03), 14 deselected** |
| Frontend | **196 passed, 2 failed (pre-existing LayoutRouting)** |
| Production build | **passes** |
| New tests this epic | **70** (61 backend, 9 frontend) |
| Live-data writes | **0** |
