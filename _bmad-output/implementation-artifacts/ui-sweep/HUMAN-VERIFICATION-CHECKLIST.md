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
- [x] **Where is the "Aliganj Branch"?** — **CLOSED 2026-07-22.** It was leftover
      sample data and was removed. Checked again on 2026-07-22: your system now
      holds exactly one branch, Joya, and all 1,802 students are on it.
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

## Epic 4 — Numbers you can believe (added 2026-07-22)

### The headline, in one paragraph

You reported that the Board Report showed zeros. **It was never a Board Report
problem.** A change made in an earlier piece of work meant that *every* screen which
reads a tool was looking in the wrong place for its answer — so eleven screens have
been showing 0 or "N/A" instead of your real figures, not one. That is fixed at the
source. Nothing you see on those screens was ever wrong in your data; the screens were
reading it wrongly.

### Needs a decision from you

- [ ] **Your school's real details — one word and they're in.** I have added the one
      thing that had nowhere to live before: your **CBSE affiliation number 2133014**
      and **school code 81936**, which now print on certificates. But four details are
      still the old made-up values in your database: the **address** (still says
      Lucknow), the **phone** (`0522-4567890`), the **email** (`info@theararyans.edu.in`,
      also misspelt) and the **principal**.
      I have the correct values ready, taken from your own website:
      *Prem Nagar, P.O. Joya, N.H. 24, Distt. Amroha, Uttar Pradesh 244222* ·
      *+91 81269 65555, +91 81269 68888* · *theaaryansjoya@gmail.com* ·
      *www.theaaryans.in* · Principal **Adesh Singh**.
      **Two ways to do it, your choice:** open School Settings and type them in (best —
      it is recorded as your change), or say the word and I will write them directly.
      **Until one of those happens, these are still wrong on your screen — I am not
      claiming otherwise.**
- [ ] **The fee structure for 2026-27.** There is now a place to record a short summary
      of your fee table so the assistant can answer parents' fee questions from it. I
      have the table from your printed sheet. Confirm it is current and I will prepare
      it for you to save. (This is a summary for the assistant to quote — it is not the
      same as loading real fee records, which is still a separate job.)
- [ ] **Sorting on the remaining tables.** You asked for column sorting on every table.
      I counted rather than guessed: **34 tables now have it**, roughly **22 do not** —
      Attendance Recorder, Exam Manager, Fee Collection, Timetable Builder, Transport,
      Principal Daily Ops and parts of the teacher and admin screens. Those are built
      differently and each needs its own work. **Say if that should be the next job.**

### Please check in the real app

**These reach your screen only after a deploy. Until then, nothing below has changed
for you.**

- [ ] **The zeros are gone.** Open Board Report, School Pulse, Fee Collection,
      Attendance Overview, Staff Tracker, Admission Funnel and Smart Alerts. Numbers
      you recognise should now appear where zeros were.
- [ ] **A student's own screens too.** Have a student open My Attendance and My
      Results — those were showing zeros for the same reason.
- [ ] **"₹0" now tells you why.** Fee collection genuinely is near zero, because your
      database holds **one fee transaction for 1,802 students**. The card now says so
      underneath, so a real zero is not mistaken for a broken screen. **If that number
      surprises you, that is a data-loading job, not a bug.**
- [ ] **Attendance before the register is taken.** Open the Board Report early in the
      morning. It should say **"not marked yet"**, never "0%". Previously it reported
      0% attendance, which reads as though nobody came to school.
- [ ] **Break one on purpose.** Turn off wifi, tap Re-generate, turn it back on. Each
      section should say it could not load, with its own **Retry** — never a zero. Tap
      Retry while still offline: the message should **change** the second time, so you
      can tell it tried again. Then check **Download PDF still works** with a section
      missing — it should print "not available" for that section rather than refuse.
- [ ] **Class Strength.** You spotted that "Other" and "Total" showed the same number.
      They should now differ: there is a separate **"Not recorded"** column, and Boys
      and Girls say **"Not recorded"** instead of 0 — because gender was never
      collected for any of the 1,802 students. Confirm that reads clearly to you.
- [ ] **Sorting.** Click any column heading on any tool screen. Check especially that
      **money sorts by amount** — on a fee defaulters list the largest debt must come
      first, not last. And check a column with blanks: empty values should sink to the
      bottom, not fill the first page.
- [ ] **Ask the assistant who the principal is.** It has **never** known — it was
      looking for the name under the wrong label. It should now answer **Adesh Singh**.
      Also ask "what is the school's affiliation number?"
- [ ] **On your phone**, for all of the above.

### Known and left alone on purpose

- **I could not verify three things myself, and I am not claiming them:** (1) how the
  exported PDF actually looks with a section missing, (2) the Class Strength counts
  against your real database — the offline test database cannot do that particular
  calculation, so I tested the rule instead of the arithmetic, and (3) anything that
  needs saving against your live data.
- **Nothing was written to your database this run.** Not one field.
- Screen tools can no longer make changes — only read. Nothing in the app used that
  ability, so you should notice no difference; it closes a door that had no lock.
- A branch manager now sees only their own branch's figures on tool screens. Previously
  they saw every branch's.

---

## Epic 10 — Real files, and reading a printed page (added 2026-07-22)

### Read this first

**Nothing in this epic is live yet.** It reaches you only after a deploy. Two parts of
it need a deploy *and* a bit of luck, and I would rather say so now than have you find
out by testing:

- [ ] **Reading printed paper needs a program installed on your server.** I have added
      the instruction that installs it, but until the deploy happens Flo will say
      "the OCR engine is not installed on this server yet". That message is deliberate:
      it must never look like "your form was blank".
- [ ] **Understanding a photograph may not work at all.** It uses the same AI service
      Flo already talks through, which may not accept pictures. Nobody has tried. If it
      cannot, Flo will say so plainly rather than making something up. **Tell me what
      it says the first time you try it** and I will know within one message.

### Please check in the real app, after the deploy

- [ ] **Ask Flo for a circular.** "Write a circular about the school reopening on 1
      April and give me a Word file." You should get a card with the file name, DOCX
      and its size, and a Download button. Open it in Word.
- [ ] **Ask for a fee sheet as Excel**, and check the columns are wide enough to read
      rather than showing ####.
- [ ] **Ask for a PowerPoint** about the school profile.
- [ ] **Hindi.** Ask for a circular in Hindi as a **Word** file - that should be
      perfect. The same thing as a **PDF** will lose the Devanagari; that is a known
      limit, not a new bug, and it needs a Hindi font added.
- [ ] **The export buttons.** Every export screen can now give you Excel instead of
      raw commas. Check a fee export opens properly in Excel.
- [ ] **An old file.** Download links expire. Open a conversation from a few days
      earlier and tap a file - it should tell you the link expired and to ask again,
      not just fail.
- [ ] **Photograph a fee slip** and send it to Flo. It should read the printed words
      back. Then photograph something with no writing on it - Flo should say it found
      no text, and should NOT pretend to describe the picture.
- [ ] **Try it as a teacher.** Reading images is for you, the Principal and the office
      staff only. A teacher should be told plainly that the image was not read.

### Known and left alone on purpose

- Flo can **read** images and **make** documents. It cannot generate images or video,
  as you asked.
- Reading a printed page costs nothing and the picture never leaves your server.
  Understanding a photograph uses the paid service, and it only happens when reading
  the words found nothing. Every use is recorded so you can see how often.
- The document tool cannot fetch data by itself. It only formats what Flo already had,
  so nobody can obtain through Flo a spreadsheet they could not already export.

---

## Change log

| Date | Epic | What was added |
|---|---|---|
| 2026-07-22 | Epic 1 | Owner-access handover decision, the live-app checks I could not make myself, and the legacy job-category question. |
| 2026-07-22 | Epic 1 + 8 | Two decisions settled by Abhimanyu (sole owner stays; no self-editing). Self-service checks replaced by ask-and-approve checks. City correction added, pending a deploy decision. |
| 2026-07-22 | Epic 9 + 3 | **Part A added: a standing ten-minute checklist to run after every epic**, at Abhimanyu's request. Plus this epic's specifics: the new look, Flo, the duplicate titles, sorting and paging, and the four live-data city corrections. |
| 2026-07-22 | Epic 10 | Real files from Flo, Excel exports, and reading printed paper. Two parts ship dark pending a deploy, and one may not work at all - both named explicitly. |
| 2026-07-22 | Epic 4 | The zeros (eleven screens, not one), honest failure states, the school's real details and affiliation number awaiting your save, the assistant finally knowing the principal, column sorting on 34 tables, and the Class Strength column you queried. Three things I could not verify myself are named explicitly. |
