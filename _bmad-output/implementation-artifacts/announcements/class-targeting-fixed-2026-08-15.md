# A notice sent to one class now reaches one class (2026-08-15)

> **LIVE, both halves together.** Backend `eduflow-classnotice-20260815-96499c9`, frontend
> Amplify job 169, commit `96499c9`. **Rollback target:
> `eduflow-approvals-20260815-69a2705`.** Bundle diffed before upload: 247 entries to 249,
> the two added being `announcement_audience.py` and migration 050, nothing removed.
> Environment Ready and Green on the new label; `/api/health/ready` answers 200 with db,
> ai, s3 and sms all ok. The three touched routes answer 401 while a made-up path under the
> same prefix answers 404 from the same server, which proves the code is live and still
> guarded. **Nothing here was proven by signing in as a real profile.**

**Abhimanyu, 2026-08-15:** fix the class targeting fault properly, with a permanent fix
covering everyone who can use the feature from their own profile.

## What was wrong

Both sending screens offer "By Class" and let you tick the classes. The chosen classes
were saved on the record, and then **no part of the platform ever read them back.**
Delivery was decided by role alone.

So a notice meant for Class 10-A was shown to **every student in the school**. Nobody lost
a message; the fault ran the other way. A notice aimed narrowly went out wide, and the
sender had no way to tell, because the screen accepted the classes and reported success.

Three further faults were found in the same place while fixing it:

1. **The parent portal filtered on two fields an announcement has never carried**
   (`audience` and `class_id`). Both were always absent, so `audience in (None, ...)`
   matched every row. Parents were shown staff-only notices, other classes' notices, and
   **drafts and rejected announcements that no one had approved.**
2. **The parent portal also pinned the parent's branch**, which announcements do not
   carry, so the two faults partly cancelled each other out. Announcements are school
   wide; that route now agrees with every other reader.
3. **Search asked only "is it a draft".** A student searching could turn up the title of a
   staff notice or another class's.

## The fix

One rule, in `backend/services/announcement_audience.py`, used by every path that writes
an announcement and every surface that reads one. Adding a screen or a Flo tool later means
calling it, not writing the rule again.

**Targeting is by class ID, never by a printed label.** The screens wrote the same class
differently: Announcements wrote `10th A`, the Circular sender wrote `10th-A`. Any fix that
compares labels has to pick a winner and silently mis-targets the other. The audience is
stored as `audience_class_ids`, resolved at write time against the school's own class list;
`audience_classes` remains beside it for display only and decides nothing. Whatever wording
a caller sends is normalised, so both screens, Flo and anything written later agree without
knowing about each other.

**Default deny.** A class-targeted announcement resolving to no classes reaches nobody, and
the write path refuses to create one. Treating it as "no restriction" is the original fault
pointing the other way: a targeting mistake would quietly become a school-wide broadcast.

**Nothing is dropped in silence.** A class that does not match is named back in a 400. A
class quietly discarded is indistinguishable from one that was delivered.

**The filter is applied by the database, not after the fact**, so the count and the paging
stay true. Filtering afterwards would make "showing 20 of 60" a lie.

Covered surfaces: the announcements list, the notification digest, the parent portal,
search, Flo's `get_announcements`, and Flo's upcoming-events calendar.

## Also changed: "Everyone" now includes the school's owner

Abhimanyu, 2026-08-15: an announcement should reach Aman and Adesh. Adesh was reached only
because the principal holds the `admin` role; **the owner was in no audience list at all**,
so a school-wide announcement never reached Aman's notifications.

The guard that stops a principal **singling out** the owner is untouched and still returns
422. It now judges what the sender asked for rather than the derived list, otherwise it
would have refused every "Everyone" notice a principal sends, which is the opposite of what
the guard is for.

## The stand-in database was lying about arrays

`$in` against a field holding a LIST was matched as "does the whole list equal one of
these", where Mongo asks "do they overlap". A stand-in kinder than the real thing
manufactures green: audience targeting would have looked broken in tests and worked in
production, or the reverse, with nothing to say which. `_value_in` in `conftest.py` now
mirrors Mongo. Same class of fault as the 2026-08-12 `insert_one` one.

## Proven, not assumed

The fix was **switched off and the tests re-run**: three of them fail with it disabled and
pass with it on. A test that passes either way proves nothing.

Gate: backend **4,016 passed / 0 failed / 14 deselected**; frontend **884 passed across 74
suites**; production build clean including lint. No live school data was read or changed.

## What this does NOT settle

**Two questions are parked with Abhimanyu, for discussion with Aman and Adesh**, and
nothing here pre-empts either:

- Should circulars reach parents and students at all, or does the messaging system already
  cover keeping families informed? Deciding that decides whether these screens keep the
  audience they have.
- Whether `announcement-broadcaster` and `circular-sender` merge into one screen. They
  remain two.

Parents keep the reach they had for their own child's class notices, narrowed to their own
child. Nothing was widened.

There are **no announcements in the live database at all**, so this changes nothing anybody
has already sent. It changes what happens the next time somebody sends one.
