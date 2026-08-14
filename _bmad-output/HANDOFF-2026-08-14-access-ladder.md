# Handoff, 2026-08-14: the access ladder restarts, and one thing must go first

**This replaces `HANDOFF-2026-08-10-release-2-after-permissions.md`, which is now history.
Read this one.**

---

## Read these, in this order

1. `CLAUDE.md`, especially the banner headed "TWO different things are called Release 3".
2. `_bmad-output/planning-artifacts/release-numbering-collision-2026-08-14.md`, which
   explains why the numbering is confusing before you meet the confusion.
3. `_bmad-output/planning-artifacts/release-3-access-department-heads-2026-08-14.md`,
   the work.
4. `_bmad-output/implementation-artifacts/release-3-access/PROGRESS.md`, the only record
   of what is done.
5. `_bmad-output/project-context.md`, the 34 patterns.

## Where everything stands

**Live and shipped:** Release 2 (Sonu and Lalit's profiles), the table release
(downloads, filters, phone sizing, shipped as "Release 3" on 12 August), and the audit
release (audit trail, undo, honest menus, shipped as "Release 4" on 13 August). Current
`main` is documentation-only commits ahead of the last deploy.

**Not shipped, not started:** the access ladder beyond step 2. Department heads and the
whole admin staff have never been switched on, and the numbering hides it.

## The one thing to understand

**`profile_matrix.py` does not gate the REST API.** It decides three things: which screens
the menu offers, which tools Flo will use, and who may export. Every REST route carries
its own hand-written gate, and `require_role("owner", "admin")` ignores the sub-category
completely, so every office desk passes it.

This was proven by probe, not read off the page. A support staff account can create a
school bus route. All three dormant office profiles can read the whole student list and
the whole staff list. Money is genuinely refused everywhere tested, which is the good news.

**"Dormant" is documentation, not a lock.** Nothing at runtime reads the `status` field.

## What is actually holding the line

Nothing in the code. **Seven office logins already exist in the live database**, created by
migration 041 on 12 August, and the only reason none of them is a live problem is that
their one-time passwords were never handed out. Abhimanyu confirmed that on 14 August.

**Four of those seven were given the accountant head's or management head's profile.** Two
assistant accountants can therefore see every teacher's salary and the whole fee ledger,
and two admin office staff hold Lalit's set, the moment either is given a password.

## What to do next, in order

> ⚠️ **This section was overtaken on the evening of 2026-08-14. R3-0 is PARKED by
> Abhimanyu's instruction and must not be started. Begin at R3-1 instead, and hand out no
> new credentials. See the update at the bottom of this file before acting on the order
> below.**

**R3-0 first, before any credential goes out.** One central check that refuses a profile
marked dormant at the door, so a dormant account gets a plain "not switched on yet" rather
than a half-working platform. Small, and it removes the class rather than the instances.

Then R3-1 (a read-only survey of every route gated by role alone), R3-2 (Chaman's profile
with no money anywhere), R3-3 (the drivers and conductors profile, defined only), R3-4
(switch Chaman on and watch him sign in). Details in the plan.

## Needs Abhimanyu, do not guess

- **Profiles for the four assistant and admin office accounts.** He is asking the school.
  Until the answer arrives, no password may be issued to those four.
- **Which profile Vipin Kumar should hold.** He is the social media executive and was given
  a `support_staff` login one day after the answer that said support staff get no logins.
  Probably a mapping choice, but confirm it.
*(Two items that stood here are now settled and were removed on 2026-08-14, rather than
left to be chased: the Zoho app password and sending mailbox arrived, so ticket email
works and was seen in a real inbox; and rotating the leaked `CRON_SECRET` is DROPPED by
Abhimanyu's decision. Do not reinstate either as an open task.)*

## Settled on 14 August. Do not reopen.

- Passwords were never handed out. Aman and Adesh have theirs; Sonu's and Lalit's go out
  on 14 August.
- Assistants get their own profiles, not the head's.
- **Messaging stops at teachers.** Students never get it. This closes the question that had
  blocked Release 5 since 10 August.
- Release 3, and as much of Release 4 as possible, lands before the credentials go out,
  with doubts left open rather than guessed.

## Rules you must not break

- Python 3.9. `from __future__ import annotations` on the first line of any file using
  `str | None`. No TypeScript; the frontend is `.js` and `.jsx` only.
- Backend tests need the database pinned or a guard stops the run:
  `MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test` then
  `backend/.venv/Scripts/python.exe -m pytest tests/backend/ -q`. **The bar is 0 failures.
  Never pin a pass count anywhere.**
- Frontend tests run from `frontend/`. `npm run build` runs lint with `--max-warnings=0`
  first, so a lint warning fails the deploy.
- **Never hand-edit `frontend/src/lib/toolPermissions.js`.** It is generated from
  `profile_matrix.py` by `scripts/generate_profile_matrix.py`.
- The pinned reach counts in `test_all_nine_profiles_sweep_r2_13.py` are the alarm. A count
  moving without a written reason means somebody's access changed and nobody decided to.
- **Grouping never grants, and nothing is ever dropped.**
- Never run `backend/migrations/run_all.py` against the live database.
- **Never write a secret to a file inside this repository.** It is public, and a scratch
  file with LayaaStat credentials was pushed on 13 August.
- The assistant is Flo. `owner` means the school's owner, Aman Litt, never Abhimanyu.
- No long dashes anywhere. Write to Abhimanyu in plain, non-technical language.

## The question worth keeping in mind

Release 4 asked whether a person can tell "nothing happened" from "we did not record it".
This release asks the neighbouring one: **can a person tell "I am not allowed" from "this
is broken"?** A dormant account that reaches six read-only screens and a Flo that can do
nothing answers that question badly.

---

## Update, 2026-08-14 evening: Release 4 is fully closed, and R3-0 is parked by decision

**R3-0 is PARKED on Abhimanyu's instruction**, not because it failed. It is built and
pushed on branch `r3-0-dormant-lock` (`033ef40`) and its own 35 tests pass. It turns 20
existing tests red, and each of those is a permission judgement rather than a chore, which
is why it was not forced through. See `implementation-artifacts/release-3-access/PROGRESS.md`
for the file-by-file list and the two questions to ask of each.

**The consequence of parking it, stated plainly so nobody has to work it out later: no
credential may be handed to anybody new.** R3-0 was the thing that made a handover safe.
Sonu and Lalit are the exception the plan already allows, because their profiles were
built and proven in Release 2 and are live. Chaman (R3-4) and the four office accounts
whose profiles the school has not yet defined must all wait.

**What holds the line meanwhile is unchanged and is not code:** nobody has a password.

### Release 4 leftovers, all four now closed

- **Ticket email works.** Through Zoho Mail, sending from `support@layaa.ai` to Abhimanyu
  and Shubham, and a real message was received. "Reconnect Gmail" is dead wording.
- **The dead Resend sender is removed and deployed.** LayaaStat commit `13fc674`, Amplify
  build 40.
- **`stat.layaa.ai` is live** over a valid certificate.
- **Rotating `CRON_SECRET` is DROPPED** by decision. Off the list for good.

### Two corrections worth carrying

- **LayaaStat is on AWS Amplify (`ddsqdblq9ge74`), not Vercel.** The repository's leftover
  `vercel.json` reads as authoritative and is not.
- **The `hello@layaa.ai` alert route is switched off**, after tracing both ends: it was a
  duplicate of the working webhook route, sent to itself, and delivered nothing in three
  attempts. Off rather than deleted, so it stays visible and one click from returning.

### Next

**R3-1, the survey.** Read-only, deploys nothing, and answers the question currently being
guessed at: how many server routes let the wrong office desk through. `POST /api/transport`
is the proven example. Nothing is widened; where a route is wrong it is written down, not
changed on the spot.
