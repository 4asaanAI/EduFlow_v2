# UI Sweep — What Abhimanyu Needs To Check Himself

Running checklist for the UI Sweep initiative (owner-reported defects,
2026-07-22). Each epic appends the things automated tests cannot decide:
real-use spot checks, judgement calls, and decisions only you can make.

Never delete a ticked item. Add a dated line to the change log at the bottom.

---

# PART A — THE STANDING CHECKLIST

**Run this after every epic, whatever the epic was about.** It takes about ten
minutes. Part B below adds the extra checks specific to each epic.

> ### ⚠️ Read this first — two ways to do real damage
>
> 1. **The local preview is wired to your LIVE system.** Anything you Save,
>    Approve, Deactivate or Delete on `localhost:3000` is a real change to real
>    records — 1,802 students and 88 staff. **Look, click, sort, page through,
>    resize. Do not save.** Where a check below genuinely needs a save, it says
>    so explicitly and you should do it on a throwaway test record.
> 2. **"It looks fine" is not the same as "it works".** Several of these ask you
>    to try to *break* something. If it does not break, that is the result.

### A1 · Does it still work at all — 2 minutes
- [ ] Sign in. The screen you land on looks right and nothing is missing.
- [ ] Open three or four different tools from the sidebar. Each one loads,
      shows real numbers, and does not show an error or a blank page.
- [ ] Open a tool, then press Back. You end up where you expect.
- [ ] Ask the assistant one ordinary question. You get a reply, not silence.

### A2 · Both themes — 2 minutes
Switch between Light Mode and Dark Mode (bottom of the sidebar) and, on the
**same** screens, check:
- [ ] Nothing disappears. No white text on a white box, no dark box on a dark page.
- [ ] Cards, boxes and the search bar are clearly separate from the background —
      not camouflaged into it.
- [ ] Small grey text is still comfortably readable, not faint.
- [ ] Buttons keep their colour and their labels stay readable on them.

### A3 · On your actual phone — 3 minutes
Not a shrunken browser window — your real phone.
- [ ] Nothing runs off the right-hand side. You never have to scroll sideways
      to read the page itself.
- [ ] Text is big enough to read without zooming.
- [ ] The menu opens, closes, and the notification bell is reachable one-handed.
- [ ] Open a long list. You can scroll it and read the column headings.
- [ ] Tap into a search or text box. **The page must not zoom in** when the
      keyboard appears.

### A4 · Lists and tables — 2 minutes
- [ ] Click a column heading. The order changes, and it re-orders the **whole**
      list, not just the rows on screen. (Sort by name and check the very last
      page — it should end in Z, not restart at A.)
- [ ] Change the rows-per-page number. It applies, and you go back to page 1.
- [ ] Leave the screen, come back. It remembers how many rows you chose.
- [ ] Empty values say something meaningful ("not recorded"), not a bare dash.

### A5 · Try to break it — 1 minute
- [ ] Try the thing this epic was meant to prevent, deliberately, as a person
      who should not be allowed to. It must refuse **clearly** — not appear to
      work, and not fail silently.
- [ ] Ask the assistant to do the same thing in plain English. It must decline.

### A6 · What I could not check myself
- [ ] Read the "Please check in the real app" list for this epic in Part B.
      Anything left unticked there is something **I have not verified** — I
      have not claimed it works.

### A7 · Say what's wrong
- [ ] Anything that looks off, screenshot it and send it. Specifically flag:
      something appearing twice, something you cannot read, something that
      moves when you click it, or a number you do not believe.

---

# PART B — EXTRA CHECKS PER EPIC

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

## Epics 9 + 3 — The new look, and long lists (added 2026-07-22)

### Settled, no action needed
- [x] **Dark mode goes back to grey**, not navy. Only the fonts, the rounded
      shapes and the accent colours came from the website.
- [x] **Flo appears in exactly three places** — the sign-in screen, the chat
      greeting, and empty/error states. Never on a working screen.
- [x] **The city is corrected in your live data.** Four stored values were
      changed with your approval: the school's city, its full address, the Joya
      branch's location, and — most importantly — **a memory the assistant had
      saved saying the school is in Lucknow.** It was answering from that.

### Needs a decision from you
- [ ] **Where is the "Aliganj Branch"?** It is stored as `Aliganj, Lucknow`.
      Aliganj is a Lucknow locality, so this looks like leftover sample data.
      I did not guess a location for a real branch. Tell me its real location,
      or tell me the branch is not real and should be removed.
- [ ] **The rest of the school's own details are still made up:** phone
      `0522-4567890`, email `info@theararyans.edu.in` (also misspelt), principal
      `Adesh`. Your own paperwork says +91-8126965555 / 8126968888 and
      theaaryansjoya@gmail.com. One word from you and I'll correct all of them.

### Please check in the real app
- [ ] **The sign-in screen.** Sign out and look at it. Flo at the top, the
      EduFlow wordmark on the card where the key symbol was. Check in both
      themes.
- [ ] **Lucknow is gone.** Refresh the Principal's login and check the sidebar
      now reads "Joya, Amroha". Then ask the assistant "where is the school?"
      and confirm it no longer says Lucknow.
- [ ] **Every tool tab shows its name once**, not twice. You found this on Staff
      Tracker, Student Database and Data Import — check a few others.
- [ ] **The message box.** Click into it. The whole rounded box should highlight.
      There should be no second blue outline drawn inside the first.
- [ ] **Sorting really sorts everything.** In Student Database, sort by name and
      go to the last page. It should end near Z. If it restarts at A, sorting is
      only reordering the visible rows and I need to know.
- [ ] **Sort by class.** The order should read NUR, LKG, UKG, 1st, 2nd … 12th —
      not 1st, 10th, 11th, 12th, 2nd.
- [ ] **Rows per page.** Change it, leave the screen, come back — it should
      remember. Set the student list to 30 and the staff list to 5, and confirm
      they stay independent of each other.
- [ ] **Buttons feel pressable** — they should sink slightly when clicked, and
      nothing around them should jump or shift.
- [ ] **Staff Tracker shows real job titles** ("Class Teacher", "Teacher",
      "Principal") — never "teacher / subject_teacher".

### Known and left alone on purpose
- Empty fields say "not recorded" rather than a dash. That is deliberate: date
  of birth, gender, house and admission date were **never collected** for any of
  the 1,802 students, so a blank would look like a fault rather than a gap.
- The audit log, notification list and fee lists have **not** been moved to the
  new sortable table yet.
- The city correction was made directly rather than through the School Settings
  screen, so it is **not in the audit log**. Future corrections of this kind
  should go through that screen so they are recorded as your action.

---

## Change log

| Date | Epic | What was added |
|---|---|---|
| 2026-07-22 | Epic 1 | Owner-access handover decision, the live-app checks I could not make myself, and the legacy job-category question. |
| 2026-07-22 | Epic 1 + 8 | Two decisions settled by Abhimanyu (sole owner stays; no self-editing). Self-service checks replaced by ask-and-approve checks. City correction added, pending a deploy decision. |
| 2026-07-22 | Epic 9 + 3 | **Part A added: a standing ten-minute checklist to run after every epic**, at Abhimanyu's request. Plus this epic's specifics: the new look, Flo, the duplicate titles, sorting and paging, and the four live-data city corrections. |
