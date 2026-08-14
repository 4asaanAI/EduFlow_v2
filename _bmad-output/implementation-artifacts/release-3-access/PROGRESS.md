# Release 3 (access) - PROGRESS

**This file is the only record of what is done. Read it first, update it last, every run.**

The work itself is in
`_bmad-output/planning-artifacts/release-3-access-department-heads-2026-08-14.md`.

**This is the ACCESS ladder step 3, department heads.** It is NOT the table and download
work that shipped under the name "Release 3" on 12 August. Two numbering schemes collided;
see `_bmad-output/planning-artifacts/release-numbering-collision-2026-08-14.md`.

Starting point: `main` at `966edeb`, clean. The table release and the audit release are
both live.

---

## Status

| Part | What it is | State |
|---|---|---|
| R3-0 | Make dormant mean something, at the door | **Not started. Do this before any credential goes out.** |
| R3-M | The staff room holds only profiles whose release has landed | **Done**, not deployed |
| R3-1 | Close the gap between the matrix and the REST API | Not started (survey first, read only) |
| R3-2 | Chaman's profile built properly, no money anywhere | Not started |
| R3-3 | The tenth profile: drivers and conductors, defined only | Not started |
| R3-4 | Switch Chaman on and watch him sign in | Not started |

Nothing is built. No live school data has been read or changed by this release.

---

## What is already true before a line is written

- **The permission thinking is DONE**, in `profile_matrix.py` and in Abhimanyu's twelve
  answers of 2026-08-11. This release builds the grants that were deliberately held back.
- **The seven office logins already exist in the live database**, created by migration 041
  on 2026-08-12. None has ever been used: all carry `must_change_password` and the
  one-time passwords were never handed out (decision 15).
- **"Dormant" is documentation, not a lock.** Proven, not assumed: a probe against the
  running application showed all three dormant office profiles can `POST /api/transport`
  and read the full student and staff lists. Money is properly refused everywhere tested.
  Full results in Part 2 of the plan.

---

## Log

### 2026-08-14 - plan written

**Did.** Recovered the access ladder from the 2026-08-09 session transcript and found it
had also been sitting in the Release 2 plan since 10 August. Established that the ladder
stopped after step 2 while two unrelated pieces of work took the numbers 3 and 4.

**Decided today (15 to 18).** Passwords were never handed out; assistants get their own
profiles with the specifics still to come from the school; **messaging stops at teachers
and students never get it**, which closes the question that had blocked Release 5 since
10 August; and Release 3 plus as much of Release 4 as possible should land before Sonu's
and Lalit's credentials go out, with doubts left open rather than guessed.

**Found by probing rather than reading.** `profile_matrix` governs menus, Flo tools and
exports. It does **not** gate the REST API, which uses hand-written checks;
`require_role("owner", "admin")` ignores the sub-category, so every office desk passes it.
A support staff account can create a school bus route. What holds the line today is that
nobody has a password, and nothing else.

**Left.** R3-0 is next and should precede any credential handover. R3-1 is a read-only
survey and changes nothing.

### 2026-08-14 (later) - the staff room now holds only the four whose release has landed

**Why.** Abhimanyu saw office staff in the colleague list who cannot sign in. Logins exist
for people whose release has not happened: the seven office accounts from migration 041
and four shared desks. Every one of them was offered as somebody to message. **A colleague
you can see and write to but who can never answer reads as being ignored**, which is worse
than their simply not being there.

**The rule he set:** a profile appears in the staff room when its release lands. Not
before, not after.

**How it is done, and why not a list of names.** `_release_has_landed` in
`routes/messaging.py` asks the permission table the question it already answers: is this
profile marked `live`? So nobody maintains a second list, and **switching a profile on for
its release lights it up in the staff room the same day, with no code change**. There is a
test that proves exactly that, by marking the transport head live and watching him appear.

`STAFF_ROLES` stays underneath as the floor. Both filters apply, so a mistake in the matrix
still cannot put a child in the staff room.

**Teachers are out too, and that is deliberate.** They are step 5 of the ladder. The four
tests written on 12 August that proved a teacher can use messaging were NOT deleted: they
now run with the teacher profile switched on, so they still prove the feature works and
they will pass unchanged when Release 5 lands. Only the date of the answer moved.

**Hiding is not refusing.** A second test proves that a dormant colleague cannot be reached
by typing their id either, not merely that they are absent from the list.

**The button follows the list.** `MessagingContext.js` drew the messaging button from role
alone, so without this the excluded profiles would have opened an empty staff room, which
looks broken rather than not-yet-theirs. It now reads the same `status` field through a new
`releaseHasLanded` helper in the generated mirror, so the button and the list cannot drift.

**Gates:** backend 3,611 passed / 0 failed / 15 deselected. Frontend 777 passed / 0 failed.
Production build clean including lint. **Not deployed.**

### 2026-08-14 (later still) - the teacher question, closed

Abhimanyu confirmed that admin staff and teachers are **counted together**, meaning
governed by the same rule, and asked directly whether that also merged their two steps of
the ladder. It does not. **Steps 4 and 5 stay separate** (decision 20). Both stay out of
the staff room and the menus until their own step lands.

No code change. The behaviour shipped earlier today was already correct under either
reading; only the roadmap was in question, and it is unchanged.
