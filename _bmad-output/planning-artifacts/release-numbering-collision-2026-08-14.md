# Two different things are both called Release 3, and both called Release 4

**Written 2026-08-14** after Abhimanyu asked whether the department heads and the admin
staff had ever been catered for. They have not, and this file explains exactly how that
happened, what state the work is actually in, and what is left.

Everything below was read from the session transcripts, the live LayaaStat and EduFlow
records, and the code. Nothing here is recalled from memory.

---

## 1. The collision

Two separate numbering schemes exist and both are recorded in this repository. Nobody
noticed they had collided.

**The original ladder**, given by Abhimanyu on 2026-08-09 after his visit to the school,
and written into `release-2-person-profiles-2026-08-10.md` at line 18. It is a **rollout
of access to more people**:

| Release | Who gets in |
|---|---|
| 1 | Aman, Adesh |
| 2 | + Sonu, Lalit |
| **3** | **+ department heads, starting with Chaman Singh (transport head)** |
| **4** | **+ whole admin staff (receptionist, IT, maintenance, support staff)** |
| 5 | + teachers |
| 6 | + students |
| 7 | + parents (may merge with 6) |

**What actually shipped under those numbers** is unrelated work that took the same names
on 11 and 12 August:

| Number | What shipped | Date |
|---|---|---|
| "Release 3" | Table filters, "all" views, downloads on every table, phone and tablet sizing | live 2026-08-12 |
| "Release 4" | Audit trail, retention, undo, the ticket route, honest menus | live 2026-08-13 |

**How it happened.** On 12 August the handover prompt for the table work opened with the
words "EduFlow Release 3" and every document, branch and commit followed it from there.
The audit work was labelled "Release 4, separate" in the same prompt. Neither prompt
mentioned the access ladder, and the ladder lived in a Release 2 document nobody was
reading by then. The two schemes never appeared on the same page until today.

**Neither piece of work was wrong or wasted.** Both shipped and both were needed. The
error is purely that the ladder was left with no numbers of its own, so the access
rollout silently stopped after Release 2 while looking as though it had gone two releases
further.

**Naming from here on.** The access ladder keeps its numbers because that is how
Abhimanyu and the school talk about it. The two shipped releases keep theirs because they
are already in commits, deploy labels and live documents. So:

- **Release 3 (access)** = department heads. **Release 4 (access)** = admin staff.
- The shipped ones are referred to as **"the table release"** and **"the audit release"**
  wherever confusion is possible.

---

## 2. What state the access ladder is really in

This is the part that matters, and it is not "nothing has been done". It is worse than
that: **a large part of Release 3 and Release 4 has already reached the live database
without anybody deciding to ship them.**

### Migration 041 was applied to the live school database on 2026-08-12

Recorded in `release-2/PROGRESS.md` in the "the data actually landed" section. It created
**seven new logins** on Abhimanyu's own instruction of that date, and the profile each was
given matters enormously:

| Person | Login | Profile given | That profile is |
|---|---|---|---|
| Sachin Yadav (assistant accountant) | `sachin.yadav` | `accountant` | **LIVE** |
| Shivam Kumar (assistant accountant) | `shivam.kumar` | `accountant` | **LIVE** |
| Sakshi Gupta (admin office) | `sakshi.gupta` | `management` | **LIVE** |
| Sameer (admin office) | `sameer` | `management` | **LIVE** |
| Vipin Kumar (social media) | `vipin.kumar` | `support_staff` | dormant |
| Asniya (front desk) | `asniya` | `receptionist` | dormant |
| Chaman Singh (transport head) | `chaman.singh` | `transport_head` | dormant |

### The finding nobody has written down before today

**`accountant` is Sonu's profile and `management` is Lalit's.** There is no separate,
narrower profile for an assistant. So the two assistant accountants hold **exactly what
the accountant head holds**, which includes every teacher's salary and increment, the
whole fee ledger and the vendor costs. The two admin office staff hold **exactly what the
management head holds**.

That was never designed, never discussed, and never written down. It is the shape of the
original Release 4 arriving early and by accident, with none of the permission thinking
that Release 2 did for Sonu and Lalit.

**What limits the harm right now:** every one of the seven was created with
`must_change_password` set, and the one-time passwords went to a handover file kept
outside this repository, for the school to distribute. **If those passwords were never
handed out, nobody has ever signed in.** That is a question for Abhimanyu, not something
the code can answer, and it is the first thing to establish.

### The three dormant ones are a different problem

`transport_head`, `receptionist` and `support_staff` are marked dormant. Dormant is
**documentation, not a lock**: nothing in the running code checks the `status` field. It
appears only in tests and in the script that generates the frontend mirror.

So what does Chaman actually get if he signs in? His profile lists six screens
(`student-database`, `transport-manager`, `transport-optimisation`, `asset-tracker`,
`custom-form-builder`, `raise-maintenance`) and **zero Flo tools, and no ability to write
anything**. He would reach a menu of six screens he can look at and not change, and a Flo
that can do nothing for him. That is not "switched off". It is a half-open door, and to
the person standing at it, it looks like a broken platform rather than a locked one.

---

## 3. What each remaining release actually needs

### Release 3 (access): department heads

The permission design is **done and written down**, in `profile_matrix.py` and in the
answers Abhimanyu gave on 2026-08-11 at the foot of
`staff-profiles-draft-for-aman-2026-08-10.md`. What remains is building the narrow things
those answers ask for, because every one of them is a grant that was deliberately held
back:

1. **A costless maintenance view for Chaman.** He arranges servicing and repairs, Sonu
   pays. He needs the maintenance calendar and the contractors' phone numbers and **no
   amount anywhere**, not a quote, not a bill, not a total. Answer 2 says this has to be
   built as a narrow view, not granted whole.
2. **Route changes without approval.** He moves a child between routes himself, recorded
   in the action log. Answer 1.
3. **Give him actual tools.** His `tool_domains` is empty, so Flo can do nothing for him.
4. **A tenth profile that does not exist yet: drivers and conductors.** Answer 10 removed
   them from support staff and gave them their own profile. The platform recognises eight
   admin desks plus the owner. This one has to be created from scratch.
5. **Decide what to do about the account that already exists.** Chaman has a live login
   today with a dormant profile behind it.

### Release 4 (access): the whole admin staff

1. **The front desk needs Commercial Operations split.** Answer 4: Asniya runs the shop
   counter, so she gets the till and nothing else, no legal entities and no reporting.
   That is one screen today and cannot be handed over in halves until it is split.
2. **The front desk needs the paid-or-unpaid flag**, cleared or outstanding, never a
   figure. Answer 5.
3. **Maintenance needs a contractor-add that touches no money.** Answer 8, wider than the
   original draft proposed.
4. **Repair approval must reuse the certificate approval built in R2-9**, not become a
   second approval system. Answer 9.
5. **No IT login while the role is held by an outside supplier.** Answer 6 is a hard stop:
   the IT person today works for Vedmarg, the school's previous ERP supplier. A standing
   login into the records of 1,876 children, held by a competing product's employee, is
   not a permission question the platform can answer. The profile switches on when a
   school employee takes the role.
6. **Support staff get no logins at all for now.** Answer 12. What matters for them is
   their data being right: their record, their attendance and their salary. Note the
   tension to check: Vipin Kumar was given a `support_staff` login in migration 041 on
   12 August, one day after that answer. He is the social media executive rather than an
   office helper, so this is probably a mapping choice rather than a contradiction, but
   it should be confirmed rather than assumed.
7. **Design proper profiles for the four people who already hold head-level access.**
   The largest single item, and the one with a live consequence today.

### Release 5: teachers

- **The screens exist.** `TeacherTools.js` is 1,142 lines and the profile lists nineteen
  screens, from attendance marking to report cards to payslips.
- **The permission entry exists** but is a shell: no Flo tools, no write ability. Deciding
  what a teacher actually holds is described in the profile's own notes as "that release's
  work, not a menu change's".
- **There is no way to create a teacher login.** The platform has exactly one login
  creation route and it is for students (`POST /api/auth/admin/students/{id}/login`).
  Every staff login so far has been made by a hand-run migration. Twelve teachers were
  deliberately left out of migration 041.
- **Messaging is already ready for them.** The old hard-wired list of four people is gone;
  anyone with a login who is an owner, admin or teacher appears in the staff directory.
- **Blocked, since 2026-08-10:** who may message whom. Teachers are already inside the
  staff messaging group, so the live part of that question is about students and parents.

### Release 6: students, and Release 7: parents

- **The screens exist.** `StudentTools.js` is 913 lines, fourteen screens, each showing a
  child only their own record. `ParentTools.js` is 106 lines and one screen, which is a
  stub by comparison.
- **Student logins CAN be created** through a real route, unlike staff. This is the one
  place where students are ahead of teachers.
- **The permission entries are shells**, same as teachers.
- **Students are NOT in the staff messaging group** and should not be. A student-to-staff
  channel is a genuinely different question and is the unanswered one.
- Release 7 may merge with 6, per the original ladder.

---

## 4. What to do first

1. **Establish whether the seven handover passwords were ever given out.** Everything else
   about the risk depends on the answer. Abhimanyu only.
2. **Decide about the four head-level accounts.** Either design assistant profiles, or
   confirm that assistants holding the head's access is intended.
3. **Answer the messaging question.** It has been open since 10 August and blocks
   Release 5 being planned at all.
4. Then plan Release 3 (access) properly, as its own document, the way Release 2 was.

---

| Date | Change |
|---|---|
| 2026-08-14 | Written. The collision found, the live state of the access ladder established from the code and the applied migrations. |
