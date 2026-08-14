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
