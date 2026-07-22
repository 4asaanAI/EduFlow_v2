# Epic 6 — Retrospective

**Date:** 2026-07-23 · **Branch:** `ui-sweep-2026-07-22`

---

## What went well

**Asking three questions before writing a line saved the epic from being wrong twice.**
The D-18 rule says ask before building anything that changes what a person may do. Two
of the three answers were **refusals** — notifications are never deleted, and nobody
reads anyone else's chats. Had I not asked, I would have built a delete button (it is
the obvious thing on a notifications page) and quite possibly an owner-wide chat view,
and both would have been discovered at the demo. The refusals are now written into the
code as comments explaining why the feature is absent, which is the only way an absence
survives the next reader.

**Eighteen of twenty-four findings arrived before any code existed.** The readiness
check, the elicitation lenses and party mode were run over the stories rather than over
a diff, so those eighteen were paid for as edits to acceptance criteria. The six that
came at epic close were all in code I had written that week. This is the first epic in
the sweep where the planning gates out-performed the review gates, and it is the
cheapest the same defects will ever be.

**Two of the findings were traps rather than bugs — code that works until it doesn't.**
The bulk-delete body typed as `List[str]` is not defensive tidiness: against an untyped
body, `{"ids": [{"$gt": ""}]}` is a request that reads "delete these three" and executes
as "delete everything you own". And the message-delete filter carries no `user_id`,
which is safe in the single-delete path *only* because ownership is proven one id at a
time first — copying that shape into a bulk path would have destroyed another user's
messages while leaving their conversation standing, with nothing in any log to explain
it. Neither would have failed a test I would naturally have written. Both came from
deliberately asking "how do I attack this?" rather than "does this work?".

**The bell had been lying since it shipped, and nobody had reported it.** It counted
`n.is_read` — a field that has never existed in this product. So the red dot appeared
whenever a person had *any* notification and never cleared, which reads as "the dot is
just decoration" rather than as a bug. The comment above the code described the
opposite behaviour, confidently. Reading what the code does rather than what its comment
claims is the fourth time in this sweep that has been the whole job.

**The `resetMocks` trap cost nothing.** Epic 5's retrospective said "before copying a
test file's setup, find out why it works". Writing that into the epic's standing notes
*before* authoring any test meant 39 frontend tests ran green first time.

---

## What did not go well

**I nearly reported a made-up baseline.** The handoff pinned 1917 passed / 2 failed; I
measured 1916 / 3 on a clean tree. The lazy responses were both available — call it
flaky, or quietly say "3 pre-existing". Instead the third failure has a real cause: the
test seeds a visitor with local time and the service computes "today" in UTC, so it
fails only between midnight and 05:30 IST. I happened to be running at 02:00. A pinned
number that silently drifts is worth less than no number, and this one would have drifted
again for the next session at a different hour.

**I claimed a defect that was not there.** I "found" backslashes in a URL path in
`api.js`, wrote a fix, and the edit failed — because the file has forward slashes and I
had misread rendered output. I checked the actual bytes only after the tool refused the
edit. If the edit had happened to apply, I would have logged a fix for a bug that never
existed, in a completed epic's name.

**The epic's own headline contradicted the Owner's decision, and I wrote both.** The
epic list promised notifications "dismissable in bulk"; two hours later I recorded his
decision that notifications are never deleted. Both sentences sat in the same document
until party mode caught it. The planning document is read as the specification by
whoever comes next — an internal contradiction in it is a defect, not a wording issue.

**One product decision was mine, not his.** The Owner asked for a typed confirmation.
I chose to make it the *count* rather than the word `DELETE`, on the reasoning that an
English keyword is a spelling test for people working in two languages. I think that is
right and the reasoning is recorded at the call site — but it is still me deciding
something about how the school works, on a destructive action. It is on his checklist
to overrule, which is the least I could do, and probably it should have been a fourth
question at the start.

---

## What changes for the next epic

1. **Verify a pinned baseline before trusting it, and explain any drift rather than
   restating a number.** Epic 7 inherits 1955 / 3, and one of those three depends on
   what time of day the suite runs.
2. **Check the bytes before believing a defect.** The cost of being wrong about a bug
   is a fix that changes working code and a log entry that misleads.
3. **Ask the product questions in one batch at the start, and include the ones that
   feel like implementation detail.** The typed-gate choice looked like a UI detail and
   was actually a decision about a destructive action.
4. **Epic 7 is the last one, and the one containing genuinely new product scope rather
   than defect repair** — a School Directory, and consolidating a long list of tools.
   The ask-before-building rule matters more there than anywhere in this sweep, and the
   evidence from this epic is that the questions are cheap and the answers change the
   design. Ask more of them, earlier, and expect some answers to be "no".
5. **Two things in this epic are verified by inspection rather than by assertion** — the
   new database index and the sidebar entry point's placement. Both are named as such on
   the human checklist. Do not let that list grow silently; an unverified item that is
   not written down is a claim.

---

## Numbers

| | |
|---|---|
| Stories | 5 |
| Owner questions asked before any code | 3 (2 answered "no") |
| Findings | **24 raised · 18 before code existed · 24 resolved · 6 dismissed with reasons** |
| — born in this epic | 6, all fixed at the gate |
| — carried into Epic 7 | **0** |
| New tests | **78** (39 backend, 39 frontend) |
| Backend suite | 1955 passed / 3 pre-existing / 14 deselected |
| Frontend suite | 244 passed / 2 pre-existing |
| Live-data writes | **0** |
