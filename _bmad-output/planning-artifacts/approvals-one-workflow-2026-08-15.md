# Approvals: one workflow for every approval on the platform

**Written 2026-08-15. NOT STARTED. Every decision below is Abhimanyu's, given 2026-08-15,
and settled. Do not reopen them.**

This is the next piece of work. It comes BEFORE handing Chaman his credentials
(decision 6 below), so R3-4 waits on this.

---

## Why this exists

R3-2 gave the transport head the ability to ask for things that need agreement: deleting a
bus route, removing a vehicle, and committing the school to a repair cost. It was built and
it works.

**Then a check found that there is no screen anywhere for Aman or Adesh to approve or
reject anything.** `getApprovalRequests` and `decideApprovalRequest` exist in the frontend's
API file and NOTHING calls them. Verified by search, not assumed. Today the only way to
decide an approval is through Flo or a raw API call.

So the platform can ask for permission and cannot receive it. That is the gap this closes.

---

## Part 1: the decisions. Settled 2026-08-15, do not reopen.

Numbered from 21 to continue the Release 3 (access) list.

### 21. ALL SIX approval systems come into one workflow, and every future one joins automatically

Not the general one first with the rest to follow. All six:

| What | Who decides it TODAY | Shape |
|---|---|---|
| General approval requests | Aman, or Adesh when routed to both | one step |
| Certificates | Aman or Adesh | one step |
| Staff leave | Aman or Adesh | one step |
| Announcements | **Aman or Adesh** (see the correction below) | one step |
| Staff profile changes | Aman or Adesh | one step, and it APPLIES the change on approval |
| **Student leave** | **a teacher first, THEN Adesh** | **two steps** |

**Abhimanyu's requirement, in his words: "even if we plan or make any more approvals in
future then those should also be covered like these 6 itself automatically."**

So this is not six screens behind one tab. It is one mechanism that the six are moved onto,
and a seventh joins by declaring itself rather than by being built again. **Any feature
added to this platform that has an approval step at any point in it is treated the same
way** (decision 25).

> **CORRECTION, 2026-08-15, made while building this.** The row above read "Adesh only"
> and that was WRONG. The code has always let the school's owner OR the principal decide
> an announcement; the table was written from memory and never checked against the route.
> Decision 22 immediately below says every kind keeps the approvers it has today, so
> **Abhimanyu confirmed the same day that it stays as the code has it, both of them.**
> Following the table would have taken a power away from the school's owner as a side
> effect of building a screen. Pinned by name in
> `tests/backend/api/test_approvals_one_workflow_2026_08_15.py`.

### 22. Each kind KEEPS the approvers it has today. A screen must never widen access

Announcements stay Adesh's alone. Student leave keeps its teacher-then-principal shape.
Nobody gains the ability to approve anything they cannot approve today.

**Abhimanyu considered making them all "Aman or Adesh, either one" and decided against it**,
with a reason worth keeping: what he actually wants from that is COVER FOR ABSENCE, so that
if one of them is away the other can act. That is a different feature from flattening the
rules, and it is **a later item and a known test case**, not part of this work.

This also carries the standing rule from Release 4: **a layout change can never widen the
permission table.**

### 23. Aman sees everything. Adesh sees enough not to be in the dark

Aman has full visibility, always.

Adesh sees Aman's decisions **wherever the matter touches him or the running of the
school**, which in practice is nearly all of it. Abhimanyu's own example, kept because it
is the clearest statement of the reasoning:

> Sonu raises a salary approval. Aman approves it. Sonu does the post-approval work. If
> Adesh had a problem with it, or simply missed it, he is in the dark about something that
> already happened in his school.

So Adesh, as principal, needs good visibility of who is raising what and who is approving
what, and of the work before and after.

**This does NOT reopen the audit-log decision.** Release 4 settled that Adesh must not see
Aman's changes in the action log, and that stands. Approvals are a different surface: both
men are approvers of the same queue, so they see the same queue. Keep the two apart.

### 24. The conversation ends when a version is approved, and an approver can re-open it

Modelled on how AWS Support cases work, which Abhimanyu named directly: **Reply**, **Resolve
Case**, **attachments** (for a bill or a quote), and a re-open.

- While pending, anybody in the approval can reply.
- Once approved, the thread closes.
- **Only somebody with the authority to approve that particular kind may re-open it.**
- Rejected is not the same as resolved: a rejection ends that version and the raiser may
  raise a new one (see decision 27).

### 25. One architecture, and every profile gets the same screen

Every profile sees the same approvals screen with the same shape. The differences are
capabilities layered on top, not different screens:

- **Aman and Adesh: approve only.** They do not raise.
- **Sonu, Lalit and Chaman, the department heads: both.** They raise to Aman and/or Adesh,
  and **later** they approve requests from the staff under them. That second half is a
  future release; the architecture has to allow for it now so it is not a rebuild.
- Everyone else sees what they raised and what involves them.

### 26. Who is in an approval's conversation

**A default per kind, PLUS anybody can be added.**

- Each kind declares who is in it by default. A repair cost includes Sonu, because he pays.
- **Both the raiser and the approver can add somebody.** Abhimanyu's reason: if the raiser
  did not add the person who is needed, the approver should be able to, and either can ask
  the other in the thread to do it.
- **When somebody is added, the person adding them CHOOSES whether the new person can read
  the conversation so far.** Exactly like being added to a WhatsApp group, where sometimes
  the history should come with you and sometimes it should not.
- **No admin role inside a thread.** Abhimanyu: it would over-complicate a simple chat.
  Revisit only if it proves genuinely necessary.

### 27. A pending approval can be edited by its raiser, and the edit is recorded

If Aman says "make it 9,000, not 12,000", Chaman changes it while it is still pending. The
change appears in the thread, so nobody can quietly alter a request after somebody has read
it.

**The approver may NOT edit the request as they approve it.** That would make the requester
and the approver the same person in one click.

### 28. Overdue is shown. Nothing is ever auto-decided

An approval left too long is flagged as overdue on the screen. It is never approved or
refused automatically. Silence is what this whole release exists to remove.

### 29. Flo is in the approvals screen, and NEVER in the shared thread

**This is the sharpest decision here and the easiest to get wrong. Read it twice.**

Every participant has Flo available while they are looking at an approval. Flo answers
**privately, to that person, on their own screen**, and **nothing Flo says ever enters the
shared transcript.**

**Why, in Abhimanyu's words:** Aman's Flo and Adesh's Flo see far more than Chaman's does.
If Flo answered into the shared thread, a question from Aman would print an answer built on
Aman's access in front of somebody who does not hold it. The permission table would be
correct and the platform would leak anyway, through the transcript.

So: **Flo is not a member of the thread.** It is a helper standing beside each person,
answering only to them, always within that person's own profile.

### 30. Flo can both RAISE and DECIDE approvals, and can answer "what is waiting on me"

Asked "are there any approvals pending for me?", Flo answers across **every kind**, and for
**both directions**: things waiting for that person to decide, and things they raised that
are waiting on somebody else. Deciding through Flo always shows a confirm card first.

### 31. Chaman waits for this

His credentials are not going out for at least two days (Abhimanyu, 2026-08-15), so R3-2
holds rather than shipping into a platform where his requests cannot be answered. **R3-4
now waits on this work, not on R3-2.**

---

## Part 2: what to take from LayaaOS and from AWS Support

Abhimanyu asked for both to be mined rather than the whole thing invented again.

**The code from LayaaOS cannot be lifted and that is not a criticism of either system.**
LayaaOS is TypeScript on Supabase with a component library and live streaming; EduFlow is
plain JavaScript on MongoDB with hand-built screens. Files copied across would not run.
**The design transfers; the code does not.** Say so plainly rather than promising reuse.

### Worth taking from LayaaOS

| Thing | Where it is | Why |
|---|---|---|
| **A clarifications thread welded to the approval** | `src/components/views/ApprovalClarificationsThread.tsx` | Exactly decision 26. Kept SEPARATE from general chat so the discussion cannot drift away from the request it belongs to. |
| **Approving carries out the action, and a failure reverts to pending** | `ApprovalsView.tsx` batch path | It refuses to leave a row reading APPROVED over something that never happened. **EduFlow already does this** as of R3-2; good to see it independently arrived at. |
| **Filters by status, and resolved items stay readable** | `StatusFilter` | Nothing is ever destroyed, matching this platform's own rule that clearing means marking read. |
| **A visible audit trail per approval** | `getAuditLog` | Who decided, when, and why. |
| **An expand-to-full-conversation control** | the thread's `Maximize2` | Useful later; not needed first. |

**Deliberately NOT taken:** tiers, timeout countdowns that auto-act, batch approve, and the
trust/quorum signature machinery. All are answers to problems a school does not have, and
batch approve in particular is at odds with decision 28.

### Worth taking from AWS Support

- **Reply**, as the ordinary action while a case is open.
- **Resolve**, as an explicit and separate act from replying.
- **Re-open**, restricted here to somebody who may approve that kind.
- **Attachments**, which the school will need for a quote or a bill.
- **One case, one thread, one running record**, readable from top to bottom afterwards.

---

## Part 3: the shape this suggests, for whoever builds it

Not a plan yet, and not agreed. Written so the next session does not start from nothing.

**One registry of approval kinds.** Each kind declares, in one place:

1. what it is called in ordinary words,
2. who may decide it, and in how many steps,
3. who is in the conversation by default,
4. what agreeing to it actually DOES,
5. whether it applies a change on approval, and how to undo that if it fails.

The screen, the notifications, Flo, and the counts all read that registry. Adding a seventh
kind is one entry.

**The largest risk, named so nobody is surprised.** Making the six behave as one means
moving six existing, working systems onto a shared shape. That is where an access accident
would come from. **Do them one at a time with the whole suite green between each**, and
never make a red test green to finish faster: decide what the person may do first. That
rule has held through R3-0, R3-1a and R3-2 and it holds here.

**Where it lives:** inside the existing Notifications window, beside the Approvals and
Notifications split built on 2026-08-15 (decision 5).

---

## Part 4: what is NOT settled and will need Abhimanyu

- **Cover for absence.** Decision 22 names it as a later item and a known test case. Nobody
  has said what it should look like.
- **Attachments.** Agreed in principle from the AWS Support shape. Where the files are
  stored, how large, and who may open them are not decided. The photo rules from the
  2026-08-15 leak work apply and must not be worked around.
- **Whether a rejected approval's thread stays readable for ever.** Decision 24 covers
  approval; rejection is implied but not stated.

| Date | Change |
|---|---|
| 2026-08-15 | Written. Decisions 21 to 31 recorded. Nothing built. |
| 2026-08-15 (later) | **BUILT and green, not deployed.** The announcements row corrected. Part 4's three open items answered by Abhimanyu: attachments ARE built, reusing the ordinary upload rules; a rejected thread stays readable for ever and cannot be re-opened; cover for absence stays a later item. Record: `implementation-artifacts/release-3-access/PROGRESS.md`. |
