"""Flo never prints a long dash. This is what makes that true rather than requested.

Abhimanyu, 2026-08-11: "make sure that Flo doesn't print them either in her replies".

The `/stop-slop` habit already tells Flo not to use them, and has since 2026-07-22 when
Abhimanyu pointed at a live reply reading "Hey Aman - how can I help..." and named the
dash as the giveaway. **A prompt rule is a request.** A language model follows it most of
the time, which is exactly the failure mode that is hard to notice: the dashes stop
appearing often enough that nobody checks, and then one turns up in a circular that has
already gone to 1,842 families.

So the rule is enforced twice. The habit tells Flo not to write them, because a model
that writes cleanly in the first place produces better sentences than one whose output is
patched. This module is the guarantee underneath, applied to every word of model text on
its way out.

**Where it is applied:** `ai/llm_client.py`, on the streamed delta and on the assembled
text. That is the single point every reply, every generated document and every drafted
message passes through, which is why it is done there rather than at the dozen places
that emit an SSE frame.

**What it does not touch:** the ordinary keyboard hyphen, which is needed for "5-A",
"class-teacher" and dates.
"""

from __future__ import annotations

# Every dash-like character wider than a hyphen. A model reaching for "a long dash"
# does not always reach for the same code point, and a rule that named only the em dash
# would be quietly satisfied by an en dash.
_LONG_DASHES = {
    "—": "-",  # em dash
    "–": "-",  # en dash
    "‒": "-",  # figure dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    "－": "-",  # fullwidth hyphen-minus
}

_TRANSLATION = str.maketrans(_LONG_DASHES)


def plain_dashes(text):
    """Replace every long dash with an ordinary hyphen. Anything else is returned as is.

    Non-string input is passed straight back, so a caller holding ``None`` or a number
    does not have to check first.
    """
    if not isinstance(text, str) or not text:
        return text
    return text.translate(_TRANSLATION)


def contains_long_dash(text) -> bool:
    """For tests and for anything that wants to assert rather than repair."""
    if not isinstance(text, str):
        return False
    return any(dash in text for dash in _LONG_DASHES)
