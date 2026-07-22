# Epics 3 + 9 — Retrospective

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

---

## What went well

**The contrast test paid for itself immediately.** It was written to satisfy an
acceptance criterion and then rejected four real colour choices on its first
run — including the brochure's own button colours, which fail WCAG outright.
Without it the app would have shipped 14px white labels at 2.65:1 and nobody
would have noticed until someone with weaker eyesight tried to use it. **A test
that computes a value beats a test that asserts a value someone typed in.**

**Building Epic 9 before Epic 3 was the right sequence.** The shared table was
built once, in the new visual language. Had they run in the documented order it
would have been built and then restyled, and the restyle would have been the
sort of cosmetic pass where regressions hide.

**Token-level fixes reached screens nobody edited.** The dark-input defect
(F-5) was reported on one screen and fixed in one file, correcting five screens
across every role. Same for the border-token-as-fill fault (F-12): found on the
send button, fixed in six places. The `--tool-hex-*` alias layer, which looked
like legacy cruft, turned out to be the lever that made a token-only retheme
reach 25 hand-styled panels.

**Refusing to guess about real-world data.** Three times the right answer was to
stop: the Aliganj branch's location was deleted rather than invented; the
principal's name was read out of the staff records rather than composed; the
crest was hidden in dark rather than recoloured, because recolouring a school's
own crest is not ours to do.

---

## What did not go well

**Eleven of fifteen findings came from Abhimanyu, not from me.** That is the
headline. He was testing live while I worked, and he found the duplicate
titles, the misaligned icons, the dark input boxes, the camouflaged borders, the
stray focus rings, the missing logo, the muddy chips and the watermark bleeding
under the sidebar. Almost all of those were visible on first render of a screen
I had just changed. **I was checking that things compiled and that tests passed,
not that they looked right.**

**Three defects in a row had the same shape: I fixed the instance, not the
class.** The duplicate title was "fixed" for desktop only — while he was
testing on a phone, so the fix was invisible to him and wrong for every role.
He had to tell me twice, and the second time he had to spell out that changes
must apply to every profile. He was right, and the correction should not have
needed to come from him. **When a defect is in a shared component, the fix is
in the shared component — and the check is "which other screens use this?"**

**I reported "Lucknow" as fixed when the screen still said Lucknow.** The code
*was* corrected, and a previous session had even predicted the stored value
would override it. But a user-visible defect is not fixed until the user sees it
change. Worse, when he pushed back the first time I explained the mechanism
instead of fixing it; he had to raise it a second time. **If a change only lands
after a deploy or a data edit, the honest word is "not yet visible to you",
never "done".**

**I broke the production build twice with the same careless edit** — appending
text after a comment's closing `*/`. Both times it passed the dev server and
failed only under minification, with an error naming neither file nor line.
Cheap to avoid, expensive to diagnose.

**The epic-close gate was not the gate Epic 1 got.** The diff never stopped
moving, so the review lenses were applied continuously rather than systematically
over a frozen diff. Findings are real; coverage is uneven. Screens the owner did
not happen to open got less scrutiny — and given his hit rate, that is a real gap.

**The mobile type scale — the whole point of UX-DR7 — has no automated test.**
Media queries do not execute in jsdom. It sits on the human checklist, which is
honest but weak for a requirement this central.

---

## What changes for the next epic

1. **After changing a shared component, list every screen that uses it and check
   a sample.** A one-line grep. Would have caught F-4, F-5 and F-12 before he
   did.
2. **Look at the thing.** Compiling and passing tests is not evidence that a
   visual change is correct. Where the owner is verifying, agree explicitly what
   he checks and what I check, so gaps are chosen rather than accidental.
3. **Never report a UI fix as done unless the UI changed.** If it needs a deploy
   or a data edit, say so in those words.
4. **Run `craco build`, not just the dev server, before calling a CSS change
   finished.** The dev server does not minify and will not catch a malformed
   selector.
5. **Freeze the diff before the close gate.** If live feedback is ongoing, do a
   dedicated systematic pass at the end anyway, and say plainly which parts were
   only reviewed continuously.
6. **Keep the standing human checklist (Part A) up to date.** It exists because
   he asked for it, and this run proved his testing is the highest-yield check
   available.

---

## Numbers

| | |
|---|---|
| Stories | 6 (Epic 3 × 3, Epic 9 × 3) |
| Findings | 15 fixed, 4 dismissed with reasons |
| — from Abhimanyu | **11** |
| — from the contrast test | 2 |
| — from the build | 2 |
| New tests | 127 (102 frontend, 25 backend) |
| Backend suite | 1745 passed / 2 pinned / 14 deselected |
| Production builds broken by me, then fixed | 2 |
| Live-data fields corrected | 8, plus 1 stale record deleted |
| Writes made without approval | 0 |
