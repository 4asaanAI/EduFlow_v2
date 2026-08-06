from __future__ import annotations

"""What Flo has to know about the documents it makes (2026-08-07).

Three things changed under Flo on 2026-08-07 and Flo would have been WRONG about all
three without being told, because a language model reasons from what the prompt says,
not from what the code does:

  1. Documents now come out on the school's own letterhead automatically. If Flo also
     writes the school name and address into the body, they print twice.
  2. Spreadsheets are deliberately NOT branded, so row one is the column headings.
     Without knowing that, Flo would treat a plain sheet as a fault and apologise for
     something that is correct.
  3. Hindi works in PDFs now. It did not before. A Flo that still believes Devanagari
     comes out as question marks will steer a school in Amroha away from writing to
     parents in Hindi, which is the exact opposite of the point of the fix.

These are prompt-content tests, which are cheap and are worth it here: the whole class
of defect they guard is the prompt and the code disagreeing (the R3 epic exists for it,
and D-13 was one).
"""

from ai.prompts import RESPONSE_FORMAT_RULES, TOOL_DRAFT_DOCUMENT

BLURB = TOOL_DRAFT_DOCUMENT["description"].lower()
RULES = RESPONSE_FORMAT_RULES.lower()


def test_flo_is_told_the_letterhead_is_already_there():
    """The failure this prevents is a duplicated header on a letter to parents."""
    assert "letterhead" in BLURB
    assert "letterhead" in RULES
    assert "twice" in BLURB or "twice" in RULES, (
        "Flo must be told WHY not to repeat the school details, not just told not to"
    )


def test_flo_is_told_spreadsheets_are_plain_on_purpose():
    for text in (BLURB, RULES):
        assert "xlsx" in text and "csv" in text
    assert "plain" in BLURB or "plain" in RULES
    assert "on purpose" in RULES or "deliberately" in RULES, (
        "a plain sheet must read as intended, not as a fault Flo should apologise for"
    )


def test_flo_is_told_hindi_now_works_in_pdfs():
    """The old behaviour was silent: Devanagari became '?' and the download still
    looked successful. Flo must not carry that stale belief forward."""
    assert "hindi" in BLURB or "devanagari" in BLURB
    assert "hindi" in RULES
    assert "pdf" in RULES


def test_flo_is_told_documents_can_be_read_and_corrected():
    """And that a correction is NOT saved back, so Flo never tells someone the school's
    stored copy has been updated when it has not."""
    assert "read and edit" in RULES
    assert "not saved back" in RULES or "not saved" in RULES


def test_flo_still_knows_to_emit_the_file_block_with_the_id_only():
    """Guard on the pre-existing rule that the 2026-08-07 additions sit next to: the
    tool returns a short id, never a link, and Flo must never invent a URL (D-37)."""
    assert "file_id" in RESPONSE_FORMAT_RULES
    assert "never write a download url" in RULES
