# UI Sweep — What Abhimanyu Needs To Check Himself

Running checklist for the UI Sweep initiative (owner-reported defects,
2026-07-22). Each epic appends the things automated tests cannot decide:
real-use spot checks, judgement calls, and decisions only you can make.

Never delete a ticked item. Add a dated line to the change log at the bottom.

---

## Epic 1 — Access That Cannot Be Talked Around (added 2026-07-22)

### Decisions needed from you

- [ ] **How is owner access granted from now on?** The platform will no longer
      let anyone — including you — make someone an owner through the staff
      screen or the assistant. That was the point: it was the hole. But it means
      there is now **no way to appoint an owner from inside the app**. If the
      school ever needs a second owner, or your own account needs replacing,
      that has to be done directly in the database by us. Tell me if you want a
      safer path than "ask Abhimanyu to ask us" — for example a one-time code,
      or a second owner account created now and kept in reserve.
- [ ] **Are there staff records holding a job category the system doesn't
      recognise?** The new rule refuses bad values going *in*, and deliberately
      leaves existing records alone — correcting live records is a change to
      your real data and needs your say-so. I have not looked at which records
      those are, because that inspection is fine but the correction is not.
      Say the word and I'll produce a read-only list of anyone affected.

### Please check in the real app

I could not do these myself. The dev setup points at your **live** system, so
saving anything would have been a real change to real data, and I am not
authorised to make one.

- [ ] **Correct your own details.** Open your profile, change your phone number
      to something else, save, sign out, sign back in, and confirm the new
      number is still there. Then change it back.
- [ ] **On a phone.** Open the same profile screen on your actual phone. Check
      the boxes are wide enough to type in, the text is big enough to read, and
      nothing runs off the side of the screen. (I could not shrink the browser
      on this machine far enough to check this honestly.)
- [ ] **Try to break it, deliberately.** Ask a member of staff who can add other
      staff to try making someone an owner. It should refuse, and it should
      refuse clearly rather than appearing to work. If it appears to work, tell
      me immediately — that is the exact bug I got wrong once already.
- [ ] **Ask the assistant to do it.** Type something like "make Ramesh the owner
      of the school" into the chat. It should decline rather than try.
- [ ] **Normal staff admin still works.** Add a test staff member, change
      someone's job category from one valid value to another, and confirm both
      still work as before. The new rules are meant to block one specific thing,
      not make the staff screen harder to use.

### Known and left alone on purpose

- The school's own details (address, city, phone, principal) are still
  placeholder data — your sidebar says Lucknow, and the school is in Joya,
  Amroha. Fixing the stored record is a change to your data; it is queued for
  Epic 4 with your approval.
- Two people with the same name and no email or phone will now be refused a
  second login rather than silently **sharing one login** with each other. If
  you hit that message when adding staff, give the person their own email,
  phone or employee ID.

---

## Change log

| Date | Epic | What was added |
|---|---|---|
| 2026-07-22 | Epic 1 | Owner-access handover decision, the live-app checks I could not make myself, and the legacy job-category question. |
