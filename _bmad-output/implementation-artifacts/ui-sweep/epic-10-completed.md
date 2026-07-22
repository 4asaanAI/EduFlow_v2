# Epic 10 — Something You Can Actually Hand Someone — COMPLETED

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`
**Owner item:** the screenshot in which Flo said it could write a Word file's *content*
but "not directly generate a real `.docx` file in this setup".
**Sequencing:** pulled ahead of Epic 5 on the owner's instruction.
**Explicitly excluded by the owner:** image and video **generation**.

---

## What was found before any code

**Flo was underselling the platform.** `python-docx`, `openpyxl`, `python-pptx` and
`fpdf2` were already pinned in `requirements.txt`. Three were used only to *read*
uploaded files; only PDF was ever used to *write*, for certificates and fee receipts.
The store-and-deliver path — S3 under `{school_id}/uploads/...`, a `file_uploads`
record, an audit row, a presigned URL — was already proven by certificates.

Nothing was missing but a place to put the writing code. That is why this was cheap
enough to pull forward.

## Story 10.1 — One place that turns content into a real file

| | |
|---|---|
| Files | `services/document_builder.py`, `services/document_export.py` (both new) |
| Tests | `test_document_builder.py` (25) |

- One builder for `docx`, `xlsx`, `pptx`, `pdf`, `csv`, `md`, `txt`.
- Tests **open each file again with its own reader**. Asserting "no exception" would
  pass for a builder that writes a truncated file, which reaches the owner as "the
  download won't open".
- **Filenames are treated as hostile** — they come from a person or from Flo. A path
  separator walks outside the school's S3 prefix; a newline forges a response header.
  Six parametrised cases cover traversal, quotes, newlines and empties.
- **Over-long exports are cut AND say so inside the file.** A silently short export is
  Epic 4's defect — a failure that looks like a complete answer — in a new place.
- Storage reuses the certificate path exactly; a build that fails stores nothing, so
  no orphan object is left in S3 with no record pointing at it.

## Story 10.2 — Flo hands you the file, not the homework

| | |
|---|---|
| Files | `ai/tool_functions_v2.py`, `ai/prompts.py` |
| Tests | `test_document_generation.py` (15) |

- Tool `draft_document`, advertised to owner, admin and teacher in four role prompts.
- **The write-classification guard rejected the first name and was right.**
  `generate_document` reads as mutating; the guard exists precisely so a mutating tool
  cannot be parked on the read-only allowlist behind an innocent name. Renamed, and
  allowlisted with the reasoning written into the allowlist itself.
- **Classification, decided rather than defaulted:** it creates a file, a
  `file_uploads` row and an audit row, but changes **no school record**. Nothing about
  a student, fee or staff member differs afterwards, so there is nothing to undo and a
  confirm step would add friction without safety.
- **Generating a document IS a data export**, so students are excluded exactly as they
  are from every endpoint in `exports.py`. A test pins that the tool **never queries
  the database itself** — that is the entire justification for its gate, and if it
  ever starts fetching, the gate must narrow.
- Daily cap **shares its counter** with certificate generation; a second counter would
  mean a second allowance.

## Story 10.3 — The file arrives where you can reach it

| | |
|---|---|
| Files | `MessageRenderer.js`, `ai/prompts.py` |
| Tests | `GeneratedFile.test.js` (9) |

- A `file` rich block renders name, type in **text** (not colour alone) and size, with
  a download control.
- **An expired presigned link says so** and tells the person to ask again, rather than
  a tap that silently does nothing.
- **Only `http(s)` is clickable.** Rich blocks are authored by the model, so
  `javascript:`, `data:`, `file:` and `vbscript:` URLs are tested and refused.
- A hostile file name renders as text, never as markup.

## Story 10.4 — The exports people already have, in the format they asked for

| | |
|---|---|
| Files | `routes/exports.py` |
| Tests | `test_exports_xlsx.py` (33) |

- All seven exports accept `format=xlsx`; **csv stays the default** so every existing
  caller keeps working.
- **Fourteen tests assert no permission moved** — a teacher still cannot export
  students or staff, a principal still cannot export fees or expenses, salary is still
  withheld, and every export still refuses a student in *both* formats.
- An unrecognised format falls back to CSV, matching Epic 3's handling of an
  unrecognised sort field.

## Story 10.5 — Flo reads a printed page, on your own server, for nothing

| | |
|---|---|
| Files | `services/ocr_service.py` (new), `routes/chat_upload.py`, `.ebextensions/04_tesseract_ocr.config`, `requirements.txt` |
| Tests | `test_ocr_service.py` (20), `test_chat_upload_ocr.py` (25) |

- **Tesseract, not PaddleOCR or EasyOCR** — those pull PaddlePaddle or Torch, hundreds
  of megabytes this instance does not have. Recorded so the choice is not revisited
  blind.
- Runs at the **upload boundary**, so Flo receives ordinary text and the chat pipeline
  needs no knowledge of images at all.
- **Three outcomes stay distinct** where a careless version returns `""` for all
  three: the engine is not installed, the page had no text, the file was not an image.
- Images are identified by **content sniffing, not file extension** — a `.png` that is
  really an archive never reaches the OCR process.
- Audited; the audit row carries counts and ids, **never the text read** — the page
  may be a child's medical note.

> **⚠️ SHIPS DARK.** `tesseract` is a system binary and is **not installed on the
> server**. Until that deploy, every request lands on "the OCR engine is not installed
> on this server yet" — which is exactly why that case is a distinct, tested answer.

## Story 10.6 — When reading the words is not enough

| | |
|---|---|
| Files | `services/vision_service.py` (new), `routes/chat_upload.py` |
| Tests | in `test_chat_upload_ocr.py` |

- **A fallback, never a parallel attempt.** The headline test asserts that when OCR
  read the text, the paid service is **not called at all**. That is what keeps printed
  paper free.
- Uses the Azure deployment Flo **already** talks through — no new service, no new
  subscription, no standing charge.
- A deployment that cannot accept images reports "this server cannot look at pictures
  yet", never an empty or invented description.
- The audit row records **whether the paid path was taken**, so the owner can see how
  often it happens rather than meeting it on a bill.

## Access rule (revised mid-epic by the owner)

**Owner, Principal and the other office staff** — accountant, receptionist and the
rest of the admin roles. **Not teachers, not students.** An earlier draft included
teachers on the reasoning that they photograph forms; the owner narrowed it to the
people who handle the paperwork. Teachers were removed **deliberately** and both the
code and the epic AC say so, so it is not "restored" as an apparent oversight.

## Test counts

| | Before | After | New |
|---|---|---|---|
| Backend | 1854 passed / 2 pinned | **1915 passed / 2 pinned** | **61** |
| Frontend | 187 passed / 2 pre-existing | **196 passed / 2 pre-existing** | **9** |

**70 new tests.** Production build passes. Scoped-filter audit clean — no new hits;
one pre-existing inconsistency in `export_expenses` annotated and logged as D-29
rather than changed, because narrowing it is a permission decision.
