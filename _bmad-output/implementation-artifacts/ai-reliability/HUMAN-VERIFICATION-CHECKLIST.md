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
- **2026-07-10 — Abhimanyu GAVE THE GO-AHEAD for FULL R10** (R10.1–R10.4 built now; R10.5 role-*widening* stays OFF — owner/principal only). Decision made before the ~2-week real-use verification in Section C was ticked — an owner override. **Action for Abhimanyu:** still work through Sections A/B/C in real use as R10 rolls out, and keep learning DISABLED via the kill-switch until you've watched the "What I've learned" panel and the turn-outcome + feedback-ratio signals for a couple of weeks.

### C-post. R10 SHIPPED (2026-07-10) — what to actually check now it's built
These are the real-use checks only a human can decide, now that R10 code is merged:
- [ ] **Open the new "What I've Learned" panel** (owner/principal → tools → "What I've Learned"). Confirm what it lists about you looks right and nothing surprising/private is there.
- [ ] **Deactivate then Reactivate** a note from the panel — confirm it disappears from active use and comes back, and **Delete** removes it for good.
- [ ] **Bulk delete** shows a preview and only deletes after you confirm (never in one tap).
- [ ] Tap **👍 Helpful / 👎 Improve** on a few replies; on Improve add a one-line note. Confirm the note shows up as a **pending suggestion** in the panel and is NOT used until you press **Activate**. Press **Reject** on one and confirm it never gets used.
- [ ] After you Activate a suggestion, confirm a later related question shows a **"🧠 remembered"** line in the reply's "Data used" footer — i.e. you can always see when a saved note influenced an answer.
- [ ] When the assistant offers to **save a routine**, confirm it only saves after you say yes, and that running it later still asks you to confirm any change it makes.
- [ ] Confirm **only you and the principal** see this panel (teachers/accountants/students do not).
- [ ] Confirm a colleague's Improve notes do **not** appear in your panel (each person reviews only what they flagged).
- [ ] **Kill-switch discipline:** keep self-learning effectively paused until you've watched the panel + the turn-outcome and Helpful/Improve signals for ~2 weeks and nothing looks off.

---

## D. 🚦 GATE — R11 (Excellence & Evaluation) — concrete post-ship checks

R11 shipped 2026-07-10. All stories are unit/integration tested. The checks below are what **only you and Shubham can confirm in the real running product**.

### R11.2 — Native Function Calling (the AI no longer guesses tool names)
- [ ] Ask the assistant a few typical queries (attendance summary, fee status, leave status). Confirm it replies with real data, not "I tried to call X" or a blank.
- [ ] Ask the assistant something off-topic ("write me a poem about Mathura"). Confirm it replies in plain text without tool errors.
- [ ] Ask something that sounds like a write action (e.g. "mark Rahul absent today") — confirm the **confirmation card** appears before anything is recorded (unchanged from before R11).
- [ ] Ask something genuinely impossible ("book me a flight") — confirm the assistant politely says it can't, rather than trying a tool and failing.

### R11.3 — True Token Streaming (faster visible replies)
- [ ] Submit a query that needs a medium-length answer (e.g. "summarise this month's attendance"). Confirm the reply **starts appearing character-by-character** (not all at once at the end). The first word should appear within a few seconds of sending.
- [ ] While a reply is streaming, let it complete normally. Confirm the message is saved in the conversation — no blank or lost reply.

### R11.4 — Hinglish / Hindi Responses
- [ ] Type a message in Hinglish (e.g. "class 5 ka attendance batao"). Confirm the reply comes back in the **same casual Hinglish register**, not pure English or formal Hindi.
- [ ] Type a message in Devanagari (e.g. "आज की हाज़िरी बताओ"). Confirm the reply is in **Devanagari Hindi**.
- [ ] Confirm that student names, amounts (₹), class labels, and dates in the answer are **not translated or transliterated** — they appear verbatim as stored in the system.

### R11.5 — Conversation Trace Viewer ("why didn't the AI reply?")
- [ ] Open the **Conversation Trace** panel (owner role only — other roles should not see it). Find a recent conversation and open its trace.
- [ ] Confirm the panel shows a timeline of turns: outcome (answered / unavailable), language detected, and which tools were called.
- [ ] Confirm the panel shows **"Layaa AI"** as the assistant name — NOT "Azure", "OpenAI", "GPT-4", or any model name. This is a confidentiality requirement.
- [ ] If you can reproduce the original incident (chat where owner got NO reply), check the trace — you should see `outcome: unavailable` with an `error_type` that explains what went wrong, visible without opening any server log.
- [ ] Confirm a teacher or accountant logged in as that role **cannot see** the Conversation Trace option in the panel menu.

### R11.6 — Residual Audit Hardening (background — no visible changes)
- [ ] No visible change expected. If you notice any fee/attendance/staff data unexpectedly appearing in an AI action log or metric panel that looks like a student name or phone number, report it — this epic tightened the PII filter.

### Confidentiality standing check (R11 permanently owns this)
- [ ] Open browser dev-tools → Network while using the chat. Confirm no response body or event-stream frame contains the words "azure", "openai", "gpt-4", or "gpt-5" (case-insensitive). The assistant must always identify as Layaa AI.

---

## E. Platform Reliability — R12 (Onboarding, Billing & Payroll)

These checks require the real running product; tests don't cover them.

### R12.1 — Owner login after provisioning
- [ ] Provision a new school through the operator panel. **Immediately** try to log in as the owner using the email address — in any case (all-caps, all-lowercase, mixed). It must work on the first attempt. *(Pre-R12, a case mismatch caused silent login failure.)*

### R12.2 + R12.3 — Billing credits land in the right place
- [ ] Make a Razorpay test payment from the Razorpay dashboard for School B. Confirm only School B's token balance increased. School A's balance must be unchanged. *(Cross-tenant isolation.)*
- [ ] Make the **first ever top-up** for a brand-new school branch that has never purchased tokens. It must succeed and show the new balance. *(Pre-R12, the first top-up always silently failed due to a MongoDB path conflict.)*

### R12.4 — Provisioning resume after partial failure
- [ ] This check is best done in a staging environment: provision a school, simulate a crash by killing the server between the DB writes, restart, and call the provision endpoint again. It should resume cleanly (200 + full login works) rather than returning 409. *(Normal users won't trigger this, but ops should confirm the retry path is safe.)*

### R12.5 — Payroll double-submit and role enforcement
- [ ] Submit a salary disbursement, then immediately submit the same form again (or replay the API call). The second call should return "already paid" with the original record. The payroll total in the UI must show one payment, not two.
- [ ] Log in as an admin with `sub_category: accounts` (the old fee-accountant role). Try to disburse a salary from the payroll section. It must be rejected (403). Only `sub_category: accountant` or owner should succeed.

---

## F. Platform Reliability — R13 (Tenancy & RBAC Fail-Closed)

### R13.2 — File serve over-exposure
- [ ] Log in as a teacher. Try to access a file URL (`/api/files/serve/{file_id}`) uploaded by a different teacher in the same school. The response must be **403 Forbidden**, not the file contents. *(Pre-R13, any authenticated user in the school could download any file by guessing the UUID.)*
- [ ] Log in as a principal. Confirm you **can** view files uploaded by any teacher in your school (cross-user access permitted for owner/principal).

### R13.3 — Export RBAC
- [ ] Log in as a teacher. Confirm the student export (`/api/export/students`) returns **403** — teachers do not have export access.
- [ ] Log in as an admin with `sub_category: accountant`. Confirm you can export fee transactions but **cannot** export the student list (owner/principal only).
- [ ] Log in as an admin with the old `sub_category: accounts` (if any such users remain in production). Confirm whether they can still export expenses. *(If they can, the data migration to rename `accounts → accountant` has not been run yet — that migration is intentionally deferred.)*

### R13.4 — Login lockout is per-school
- [ ] If you run a multi-school instance: trigger several bad-password attempts for a user in School A. Confirm the **same email in School B is not locked out**. *(Pre-R13, a global lockout key was shared across all schools.)*

### R13.7 — Staff deactivation kills sessions
- [ ] Deactivate a staff member's account from the staff management panel. Then log in as that staff member (or have them attempt to use an existing session). Their **existing session must be rejected** — they cannot continue using a tab that was open before deactivation. *(Pre-R13, refresh tokens were not revoked on deactivation.)*

### R13.8 — SMS daily cap
- [ ] If possible in staging: send bulk SMS reminders until you approach the daily cap (default 1000 per school). The API should return a **429 "Daily SMS limit reached"** response rather than continuing to charge. The cap is configurable via `SMS_DAILY_CAP_PER_SCHOOL` env var.

---

## G. Platform Reliability — R14 (Multi-Worker Correctness)

### R14.1 — Multi-worker SSE startup guard
- [ ] **Confirm EB deployment uses WEB_CONCURRENCY=1.** Check the Elastic Beanstalk environment's `WEB_CONCURRENCY` environment variable (or Procfile/gunicorn.conf). It must be 1 (or unset) unless you have Redis configured (`REDIS_URL`). If it is > 1 with no Redis, the app will now refuse to start and return an error — that is the intended behavior. *(Pre-R14, the app would silently start but notifications would be dropped for users on different workers.)*

### R14.2 — School deactivation gate
- [ ] This check is background-only: the school status lookup is now cached for 30 seconds. If you need a deactivated school to take effect faster, call the operator panel to deactivate and verify that within 30 seconds the affected school's users start receiving 402 responses. No functional change should be visible to users of active schools.

---

## H. Platform Reliability — R15 (Residual Confirmatory Sweep)

### R15.5 — Manual attendance duplicate no longer errors
- [ ] Record a manual attendance entry for a student on a date, then submit the **same** entry again. The second submit should be accepted quietly (no error). Now submit a **different status** for the same student+date — you should get a clear "already exists — use correction" message (not a server error), and be able to change it via the correction flow. *(Pre-R15 the duplicate surfaced as a generic 500.)*

### R15.5 — Houses page shows exactly four
- [ ] On a brand-new school, open the Activities / Houses screen. Confirm exactly **four houses** (Blue, Green, Red, Yellow) appear — never duplicates — even if two people open it at the same moment on first load.

### R15.4 — Seed-status locked down in production
- [ ] In production, open `/api/auth/seed-status` in a browser **without logging in**. It must be **refused** (not show row counts). Only a logged-in owner can see it. In dev/staging it stays open (used by seed scripts). *(Pre-R15 it exposed user/student/staff counts to anyone.)*

### R15.3 — In-app help assistant RETIRED (post-R15, 2026-07-10)
- [ ] The little floating help chatbot (the "how do I…" helper button) has been **removed from every profile** — it was redundant because every dashboard profile already has the full AI chat. Confirm the floating button is gone and the main chat still works normally on each role's home screen. *(The R15 rate-limit/metering work on that helper is now moot — the endpoint no longer exists, which is a strictly safer outcome for cost.)*

### R15.2 — Guardian contact visibility (PRODUCT DECISION NEEDED)
- [ ] **Decide:** should a **teacher** be able to see a student's guardian **phone/email** in the student record? Today staff (owner/admin/teacher) can, because contacting guardians is a normal need; the student's own self-view already hides income/occupation. If you want guardian contact restricted to certain roles only, that's a small follow-up change — flag it and we'll scope it. (No code changed in R15; this is a policy call, not a bug.)

---

## I. Future items — added as the initiative progresses

_(The executing agent appends new human-verification items here at each epic close.
Nothing that needs your eyes should live only in a chat transcript.)_

---

## Change log
- **2026-07-10** — Document created (after R9 shipped). Seeded sections A–D: standing checks, R1–R9 post-ship spot-checks, the R10 go/no-go gate, and an R11 placeholder. — executing agent
- **2026-07-10** — R10 shipped (full self-learning phase 2). Appended §C-post: concrete real-use checks for the new "What I've Learned" panel, feedback→learning loop, routine saving, recalled-memory disclosure, and the cross-user/role privacy checks. Keep learning paused via kill-switch until the panel + signals are watched for ~2 weeks. — executing agent
- **2026-07-10** — R11 shipped (excellence & evaluation — final epic). Replaced §D placeholder with concrete real-use checks for native FC (R11.2), streaming latency (R11.3), Hinglish/Hindi (R11.4), conversation trace viewer + confidentiality (R11.5), residual hardening (R11.6). Confidentiality standing check added as a permanent verification item. **Initiative complete.** — executing agent
- **2026-07-10** — R12 shipped (onboarding, billing & payroll integrity). Added §E with 5 real-product verification items: owner login, Razorpay cross-tenant isolation, first-topup success, provisioning resume, and payroll double-submit + role enforcement. — executing agent
- **2026-07-10** — R13 shipped (tenancy & RBAC fail-closed). Added §F with 6 real-product checks: file serve over-exposure (least-exposure), export RBAC, per-school login lockout, staff-deactivation session revocation, SMS daily cap. — executing agent
- **2026-07-10** — R14 shipped (multi-worker correctness). No new human-verification items — the SSE startup guard is an ops/config concern (set WEB_CONCURRENCY=1 or REDIS_URL); the school status cache change is invisible to end users (same behavior, bounded latency). The §F R14 check below covers the one observable change. — executing agent
- **2026-07-10** — R15 shipped (residual confirmatory sweep — final epic of the Platform Reliability initiative). Added §H with 5 checks: manual-attendance-duplicate no longer errors, houses page shows exactly four, seed-status locked down in production, in-app help assistant is capped + metered, and one **product decision** (guardian contact visibility to teachers). Relabeled the future-items placeholder to §I. — executing agent
- **2026-07-10 (post-R15 follow-up)** — On owner instruction, the redundant in-app help chatbot was fully retired (floating widget removed from all profiles + `/api/assistant` backend endpoint + tests deleted), since every dashboard profile already has the main AI chat. Updated the §H R15.3 check to a verification that the widget is gone. Suite 1632→1625 (−7 assistant tests). — executing agent
