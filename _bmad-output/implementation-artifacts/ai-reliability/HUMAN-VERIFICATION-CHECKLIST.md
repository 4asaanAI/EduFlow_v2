# AI Reliability — Human Verification Checklist (Abhimanyu / Shubham)

**Owner:** Abhimanyu · **Started:** 2026-07-10 · **Status:** living document

## What this is (read once)

The automated test suite proves the **code** is correct. This document is the other
half: the checks that only a **human using the real product** can sign off — things
like "did the incident actually stop happening in real use", "are we comfortable with
the privacy story", and the **go/no-go gates** before risky epics.

**How to use it**
- Each item is a checkbox with *why it matters* and *how to check it* in plain terms.
- Tick a box only after you've verified it **in the running product** (not in a demo).
- Sections marked **🚦 GATE** must be fully ticked before that epic is allowed to start.
- Add a date + your initials next to anything you tick, so we have a record.

**How this doc stays current:** the executing agent adds new human-check items here at
the end of **every epic** (this is written into the execution protocol so it happens on
every run, in any session). If you ever spot something to verify that isn't listed,
tell the agent and it gets added here.

---

## A. Standing checks — keep an eye on these continuously (especially after any deploy)

- [ ] **The assistant never goes silent.** Every chat message gets either a real answer, a clear "I hit a problem — try again", or a confirm card. If anyone reports "I sent a message and *nothing* came back", that's the original incident — flag it immediately.
- [ ] **Confirmed actions match reality.** When the assistant says "done" (fee recorded, attendance marked, leave approved), the underlying record actually reflects it; a failure says "failed", never a false "done".
- [ ] **No data crosses boundaries.** No one sees another branch's or another school's students/fees/staff.
- [ ] **The app is actually up (not silently AI-dead).** After a deploy, confirm the assistant is answering — the server now refuses to boot if the AI key/endpoint is missing, so a silent "AI is down but nobody noticed" should no longer be possible.

---

## B. Post-ship spot-checks for what shipped (R1–R9) — verify in real use

Do these once in the live product with a real owner/principal account. They confirm the
shipped fixes actually behave for real users, not just in tests.

- [ ] **R1 (never silent):** ask something vague or odd → you still get a reply or a clear error with a Retry, never a blank.
- [ ] **R2 (writes are honest):** record a fee or mark attendance via chat → the record matches; try one that should fail (e.g. a student who doesn't exist) → it says it failed.
- [ ] **R3 (right tools per role):** each role's `/` tool menu works without "tool not available" surprises; an accountant login does **not** see principal-only reports.
- [ ] **R4 (denied ≠ empty):** ask for something your role can't access → you get "you don't have access", **not** a misleading "there are none".
- [ ] **R5 (branch isolation):** a branch-bound admin sees only their branch; the owner sees all branches.
- [ ] **R6 (memory is safe):** typing "delete student Rahul" performs the *action* (or asks to confirm the delete) — it is **not** swallowed as "Got it, I'll remember that"; deleting a saved note shows you which note and asks first.
- [ ] **R7 (numbers are right):** pick a fee total, an attendance %, and an exam pass-rate the assistant reports and check them against the matching tool panel — they agree.
- [ ] **R8 (chat recovers gracefully):** turn off wifi mid-reply → you get a "connection lost, retry" not a blank; when AI usage runs out you get a visible message; tables and links in replies render properly and links are clickable.
- [ ] **R9 (guardrails don't over-block; certs locked down):** a student can get help with "the atomic bombing of Hiroshima" essay and a student genuinely named *Dan* isn't blocked; only the **owner or principal** can generate a certificate/ID card, and the certificate shows the **real** student's name from records (you can't type in an arbitrary name).

---

## C. 🚦 GATE — R10 (Self-Learning) go / no-go

**Why gated:** R10 is the first epic where the assistant *changes its own future
behaviour from what it has seen* — it remembers preferences, learns from 👍/👎, and can
save "routines". A mistake here compounds quietly over weeks, so we verify the safety net
is holding in real use before switching it on.

**1. Foundation working in real use (not just tests)**
- [ ] The silent-no-reply incident has **not recurred** in real use.
- [ ] Confirmed actions consistently match the records.
- [ ] No cross-branch / cross-school data reported.
- [ ] Owner + principal have used the assistant enough over ~2 weeks to genuinely trust it.

**2. Memory safety proven (R10 builds on this)**
- [ ] "delete student…" / "note attendance…" run as actions, not swallowed as memories.
- [ ] Deleting a saved note asks first and deletes only what it showed.
- [ ] No private data (phone/Aadhaar/medical) appearing in replies where it shouldn't.
- [ ] Removing a person actually erases what the AI learned about them (DPDP erase).

**3. We + the school want self-learning, privacy eyes open**
- [ ] Comfortable the assistant will retain preferences and learn from feedback.
- [ ] Clear answer for parents/regulators on what's stored about people and how it's erased (children's data / DPDP).
- [ ] Agreement on who may see/edit what the AI learned (plan restricts to owner/principal).

**4. Operational readiness before flipping on**
- [ ] We can turn learning **off instantly** if it misbehaves.
- [ ] We start **owner/principal only** — no widening to teachers/students this phase.
- [ ] We agree to watch the turn-outcome counter and the Helpful/Improve ratio for ~2 weeks after enabling.

**Recommended rollout if this gate clears:** approve R10 in two steps — (1) durable memory
+ the "What I've learned" transparency panel first, so you can *see* what it learns before
trusting the loop; (2) the feedback-learning and saved-routines once the panel shows nothing
surprising. Widening beyond owner/principal (R10.5) stays a separate later decision.

**Decision log:**
- _(unfilled)_ — R10 go/no-go decision: ____ (date / who / notes)

---

## D. 🚦 GATE — R11 (Excellence & Evaluation) — human checks _(to be detailed when R11 is scheduled)_

R11 is about quality, speed, language, and debuggability. Human checks will likely include:
- [ ] Replies read well and are genuinely helpful (not just correct) across roles.
- [ ] Hinglish / Hindi questions are handled naturally (UP school context).
- [ ] The assistant feels fast enough in day-to-day use.
- [ ] (Agent to expand this section with concrete items when R11 stories are executed.)

---

## E. Future items — added as the initiative progresses

_(The executing agent appends new human-verification items here at each epic close.
Nothing that needs your eyes should live only in a chat transcript.)_

---

## Change log
- **2026-07-10** — Document created (after R9 shipped). Seeded sections A–D: standing checks, R1–R9 post-ship spot-checks, the R10 go/no-go gate, and an R11 placeholder. — executing agent
