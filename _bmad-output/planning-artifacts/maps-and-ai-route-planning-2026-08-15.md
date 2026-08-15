# Maps on screen, and AI route planning. PARKED 2026-08-15, waiting on Aman

**Asked for by Abhimanyu on 2026-08-15.** Parked the same day by his own decision, and the
reasoning is his and is worth keeping in his own terms:

> if it is going to cost money then it would obviously be included in his sub cost and he
> might not want to pay additional cost for a redundant tool that he might not even use

So three things at once, and all three matter. **It costs money.** **That cost lands in
Aman's SUBSCRIPTION, not in Layaa AI's budget**, which makes it his decision and not one to
be made for him. And **the school already has working routes**, so this could be paid for
and never pressed.

He is asking Aman before anything is built.

**Nothing has been built. No key has been bought. No Google account has been opened.**

---

## What was asked for

A real map inside the platform, for Chaman, Aman and Adesh together. Drop pins for where
children live. Record how many vehicles of each kind there are, buses, vans, autos, and how
many drivers. Then let the AI look at all of that and propose whole route plans: the
cheapest, the most fuel efficient, and so on. Each plan would assign children and teachers
to vehicles by itself. The three of them look at the options and agree on one. Not a
replacement for the routes they run today, an option for when they want it.

---

## What already exists, found by reading the code on 2026-08-15

More than expected. About a third of the groundwork is in place.

- **A Google Maps connection is already written**, `backend/services/maps_service.py`. It
  turns an address into a map point. It is switched off in production because
  `GOOGLE_MAPS_API_KEY` is not set on the server.
- **Children already have a place to store a map pin** (`coordinates` on the student
  record), and routes already have a centre point (`centroid`).
- **A screen already exists**, Route Optimisation, with three tabs: look up an address,
  suggest the nearest route for one child, and a clustering view.
- **Vehicles already exist as records** with a number, a type of bus, van or auto, a
  capacity, and a driver name and phone.

## What does not exist

- **No map is drawn anywhere.** Every one of the above is text boxes and lists. Nobody can
  see the school and the children on one picture.
- **Distances are straight lines, not roads.** Fine for "this child is nearer route B".
  Useless for "this route saves fuel".
- **Almost certainly not one pin has ever been set.** 1,842 active children. This is the
  largest single piece of the whole request and it is data entry, not AI.
- **Drivers are a name and a phone on a vehicle**, not people. No count, no shifts, no
  licences.
- **Nothing on a vehicle says what it costs to run.** No fuel figure, no mileage, no
  owned-or-hired.
- **Teachers cannot be put on a route at all.** Only children have a route field.
- **There is no "three people look at options and pick one" step.** That is entirely new.

---

## The conflict that WAS here is GONE. Do not reintroduce it

This section used to say the transport head may see **no amount anywhere** (settled
2026-08-11), and that "the most cost effective route" is therefore a money answer he
cannot be shown. It offered three ways round it.

**All of that is dead. Abhimanyu reversed it on 2026-08-15: the transport head holds FULL
financial visibility of school TRANSPORT**, fares and who owes what included. Option 2 of
the three, the one described above as "a real change to the 11 August decision", is what
he chose.

So a route plan may name what it costs, in rupees, on Chaman's screen. **The boundary that
does still stand is that it is TRANSPORT money and nothing else**: not tuition, not
concessions, not salaries. A plan that quoted a saving against the school's whole budget
would cross it.

---

## The open questions, kept for when this is unparked

**Money and the account**

- Google Maps is a paid Google service needing a Google Cloud account with a card. The Azure
  startup credits do not cover it. Whose card, and is there an existing Google Cloud project?
- Rough size: pinning 1,842 addresses once is a few thousand rupees. Road-distance route
  planning is charged per calculation and can run into real money if the button is pressed
  repeatedly.
- A hard spend cap on the key from day one, so a mistake cannot run up a bill.

**Getting the children onto the map, the real work**

- Who does 1,842 pins? Guess from the addresses on file and correct the bad ones, or Chaman
  by hand over time, or parents place their own pin from the parent portal.
- Are the addresses on file good enough to guess from? If most read like "near the temple,
  Joya", guessing will fail and should not be built.

**Privacy**

- A map of where every child lives is the most sensitive screen this platform would hold.
  Should Chaman see all 1,842 homes, or only children already on a bus?
- Should parents be told their child's home is being pinned? My view is yes, and it is one
  line in the portal.

**Vehicles and drivers**

- How many buses, vans and autos, and how many seats each. Fuel figures. Any hired rather
  than owned.
- Do drivers become proper records now? Note this overlaps R3-3, which already says drivers
  and conductors get their own profile.
- Do teachers actually travel on the school buses, and is it the same teacher on the same
  route each day?

**How the deciding works**

- Suggested shape: Chaman asks for options, all three can open and comment, only Aman or
  Adesh can apply one. Applying moves children onto new routes in one go, recorded in the
  action log, reversible for a period.
- Does applying a plan notify the affected families automatically, or is that a separate
  deliberate send?

---

## Where this sits

**Behind the approvals workflow, then R3-4.** Chaman's profile (R3-2) and the tenth profile
(R3-3) are built and green and deliberately undeployed; his login (R3-4) now waits on
`approvals-one-workflow-2026-08-15.md`. This work should land on somebody who already has a
working login, not the other way round.

**And behind Aman's answer.** If he does not want to pay for it, this document is the
record of what was considered and why it was not built, which is worth more than a
half-finished feature.

| Date | Change |
|---|---|
| 2026-08-15 | Written and parked. Nothing built, no key bought, no account opened. |
| 2026-08-15 (later) | Corrected. The "Chaman sees no money" conflict is REMOVED: he now holds full transport financial visibility, so a route plan may quote rupees to him. Abhimanyu's parking reason recorded in his own words. Order updated: R3-4 now waits on the approvals workflow. |
