# Epic 5 — Retrospective

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

---

## What went well

**Checking what was already fixed before writing stories.** Two of the four owner items
turned out to be handled by earlier work — the composer by Epic 9, the stream
resilience by epic R8. Writing stories for them would have produced churn in the chat
surface, which is the most safety-critical code in the product and the place a
regression hurts most. The epic is small because the honest scope was small.

**The alignment defect was fixed as a value, not as a look.** Three stacked elements at
42px, 0px and 42px is exactly the kind of thing that survives a screenshot review
because it looks *almost* right. Exporting `STREAM_GUTTER` and asserting it in a test
turns "does this look aligned?" into a question with an answer.

**Finding the duplicate progress boxes by reading the render path rather than the
symptom.** The owner's report was "overlapping progress boxes". The cause was that two
components were fed the same tool events from different sources. That is only visible
by reading what feeds each one, and it is the fourth epic running where the reported
symptom and the actual defect were different things.

**Distinguishing "still working" from "nothing is coming".** The easy version of a
stall watchdog says "something went wrong" at one threshold. That would send the owner
to retry a request that was about to succeed. Two thresholds and the keepalive as proof
of life cost a few extra lines and make the message truthful.

---

## What did not go well

**All nine of my tests failed on the first run for a reason unrelated to the code.**
CRA's jest config sets `resetMocks: true`, which wipes the implementations declared in
a module factory. The existing chat test file survives it only by accident — it uses a
teacher, and the widget that trips over the missing mock returns early for teachers. I
copied the file's shape without understanding why it worked.

**The thresholds are judgements presented as numbers.** 12 seconds and 45 seconds are
guesses that look precise. They are marked as unverified on the human checklist, but a
reader of the code sees two exported constants and no indication that nobody has
watched a real connection at a real school on a real morning.

**This epic could have been merged into a check rather than an epic.** Two stories, one
file, nine tests. The one-epic-per-run protocol served the large epics well and made
this one feel heavier than the work justified.

---

## What changes for the next epic

1. **Before copying a test file's setup, find out why it works.** The existing chat
   test passes for a reason that does not generalise, and I inherited the bug.
2. **When a constant encodes a judgement, say so where it is defined.** `STALL_SLOW_MS`
   should read as "12s, a guess, unverified against a real connection" — which it now
   does, but only after the retrospective.
3. **Check what earlier epics already fixed before writing stories.** It saved a
   rebuild of the composer here and would have saved time in at least two prior epics.
4. Epics 6 and 7 remain, and Epic 7 contains genuinely new product scope rather than
   defect repair — it is the one that most needs the ask-before-building rule.

---

## Numbers

| | |
|---|---|
| Stories | 2 (from 4 owner items; 2 were already fixed by earlier work) |
| Findings | 4 fixed, 4 dismissed with reasons |
| — introduced by this epic | 1 (my own test setup) |
| New tests | **9** |
| Backend suite | 1915 passed / 2 pinned (unchanged — no backend files touched) |
| Frontend suite | 205 passed / 2 pre-existing |
| Live-data writes | **0** |
