# UI Sweep — What Abhimanyu Needs To Check Himself

Running checklist for the UI Sweep initiative (owner-reported defects,
2026-07-22). Each epic appends the things automated tests cannot decide:
real-use spot checks, judgement calls, and decisions only you can make.

Never delete a ticked item. Add a dated line to the change log at the bottom.

---

## Epic 1 — Access That Cannot Be Talked Around (added 2026-07-22)

### Decisions — SETTLED 2026-07-22

- [x] **A second owner is not wanted.** Aman Litt stays the sole owner. Noted,
      and the platform now protects that in both directions: nobody can be made
      an owner, and the existing owner cannot be demoted either. If that ever
      needs to change it has to be done directly in the database by us.
- [x] **Staff must not edit their own details.** Reversed on your instruction.
      Nobody — not even you — can change their own record from their profile.
      People can now *ask*, and you or the Principal approve it.

### Still needs a decision from you

- [ ] **Are there staff records holding a job category the system doesn't
      recognise?** The new rule refuses bad values going *in*, and deliberately
      leaves existing records alone — correcting live records is a change to
      your real data and needs your say-so. Say the word and I'll produce a
      read-only list of anyone affected.
- [ ] **Should the city change be deployed?** I corrected "Lucknow" to
      "Joya, Amroha" everywhere it was written into the code, including in the
      assistant's own briefing — it had been told the school is in Lucknow.
      Nothing was written to your database. This reaches your live site only
      when we deploy, which needs your go-ahead. **If the sidebar still says
      Lucknow after the deploy**, that means the wrong city is also saved in
      your database, and correcting that is a separate one-line data change I
      would need your approval for.

### Please check in the real app

I could not do these myself: the only working setup points at your **live**
system, so saving anything would have been a real change to real data.

- [ ] **On a phone.** Open your profile on your actual phone. Check the text is
      big enough to read and nothing runs off the side. (I could not shrink the
      browser on this machine far enough to check this honestly. You are the
      only one who can do it until we have a safe test setup.)
- [ ] **Ask for a correction.** Get a teacher to open their profile, tap "Ask
      for a correction", change their phone number and send it. Confirm: their
      details do **not** change, you get a notification, and it appears under
      Corrections on the staff screen. Approve it, and confirm the number
      updates and stays updated after they sign out and back in.
- [ ] **Reject one too**, and confirm nothing changes and they are told.
- [ ] **Try to break it, deliberately.** Ask a member of staff who can add other
      staff to try making someone an owner. It should refuse, and refuse
      clearly rather than appearing to work. If it appears to work, tell me
      immediately — that is the exact bug I got wrong once already.
- [ ] **Ask the assistant to do it.** Type something like "make Ramesh the owner
      of the school" into the chat. It should decline rather than try.
- [ ] **Normal staff admin still works.** Add a test staff member and change
      someone's job category from one valid value to another. The new rules are
      meant to block one specific thing, not make the staff screen harder to use.

### Known and left alone on purpose

- The school's address, phone and principal are still placeholder data in your
  database. Queued for Epic 4, with your approval.
- Two people with the same name and no email or phone will now be refused a
  second login rather than silently **sharing one login** with each other. If
  you hit that message when adding staff, give the person their own email,
  phone or employee ID.
- **A Principal cannot approve their own requested correction** — otherwise the
  approval step would mean nothing for them. Theirs come to you.

---

## Change log

| Date | Epic | What was added |
|---|---|---|
| 2026-07-22 | Epic 1 | Owner-access handover decision, the live-app checks I could not make myself, and the legacy job-category question. |
| 2026-07-22 | Epic 1 + 8 | Two decisions settled by Abhimanyu (sole owner stays; no self-editing). Self-service checks replaced by ask-and-approve checks. City correction added, pending a deploy decision. |
