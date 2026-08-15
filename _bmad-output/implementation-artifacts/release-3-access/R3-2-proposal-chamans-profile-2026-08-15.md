# R3-2: what Chaman Singh should hold. APPROVED by Abhimanyu 2026-08-15

**Written 2026-08-15 as a proposal. ANSWERED the same day; the answers are in Part 0 and
they OVERRIDE the proposal below wherever the two disagree.** This exists because the
handoff is explicit: which Flo tools Chaman gets is a GRANT, and a grant is written down
and approved before it is built, never decided silently.

---

## Part 0: Abhimanyu's answers, 2026-08-15. Settled. These win.

**A. He gets full financial visibility of school transport, INCLUDING who owes what.**
This overturns the whole of Part 1 below. The fare is his, transport running costs are
his, and the transport fee status of families on his routes is his, amounts included.
The reasoning: he is the transport head and that much authority is his to hold.

**Scope, so it does not creep.** Transport money only. Not school fees, not tuition, not
salaries, not any other part of the school's finances. A family's transport fee, and
nothing else about that family's bill.

**B. Children on a bus only, not the whole roll.** He sees the address and guardian
numbers of children assigned to a route. Confirmed: the roster already returns children by
route and every child record carries which route they are on, so this is a filter he
cannot switch off, not a new feature.

**C. He may delete, and a deletion needs approval from Aman OR Adesh, either one.**
Deleting a route, a vehicle, a driver or a conductor. Not both approvers, either. This
reuses the approval flow that already exists rather than becoming a second one.

**D. Drivers and conductors go onto the staff roll, with no logins.** Confirmed against
the code before building: the Add Staff form already offers a staff type of
**"Transport"** beside Teacher, Admin and Support, and the platform already counts people
as "Non-teaching". So they get proper staff records the same way support staff do, and
they appear in the directory and the counts. **No login for any of them**, which keeps the
answer of 2026-08-11 intact.

**E. Vehicle repair costs yes, building repairs no.** He sees what a bus repair costs
because transport money is his. He does not see repair costs for buildings and other
school property.

**F. A repair cost must be approved before it is charged.** He proposes what it will cost
and Aman or Adesh agrees the figure before the money is committed. Same either-one rule as
the deletions.

**G. Both faults found while surveying are to be fixed**, plus anything else of the same
shape: the maintenance screens treating an office account with no job title as if it were
the principal, and any signed-in account being able to read a single repair request by its
id including its amounts.

---

**Everything below this line is the original proposal, kept as written.** Where Part 0
disagrees with it, Part 0 wins. The clearest case is Part 1: it argued the fare had to be
taken away from him, and the answer is that he keeps it.

Read this with two things beside it:

- Answers 1 and 2 of `staff-profiles-draft-for-aman-2026-08-10.md`, given 2026-08-11.
  He moves a child between routes himself with no approval step; he arranges vehicle
  servicing and Sonu pays, so he needs the calendar and the contractors' numbers and
  **no amount anywhere**.
- The eleven transport tests listed in `R3-0-retired-and-the-twenty-questions-2026-08-14.md`,
  which are the map of what he can already do.

---

## Part 1: the thing that has to be decided first, because it breaks decision 2 on day one

**A bus route carries a monthly fare, and the transport screen shows it.**

This is not a small detail and it is not avoidable by choosing a different screen. Proven
by reading, not assumed:

| Where | What it shows |
|---|---|
| `AdminTools.js` route table | a column reading `₹<fare>` on every route |
| `AdminTools.js` route detail | a `Fare: ₹...` line |
| `AdminTools.js` Add Route form | a field labelled `Fare (₹)` |
| `get_transport_status`, the Flo tool | returns `fare` on every route |
| `create_transport_route` / `update_transport_route` | accept `fare` as a parameter |

So granting Chaman the transport screen exactly as it stands hands him a rupee figure on
the first screen he opens, and hands him the ability to change what families pay. Answer 2
says no amount anywhere, and answer 1 of the draft says plainly: he decides who rides which
bus, Sonu decides what that costs.

**What I propose, and I want this confirmed rather than assumed.**

**The fare is not Chaman's field at all.** Not hidden behind a toggle, not shown as a dash.
Removed from his version of the screen, absent from his Add Route form, stripped out of
what Flo tells him, and **refused by the server if a request from his profile carries it**.
The last part matters most: hiding a field on screen while the server still accepts it is
the same class of fault this whole release is about.

Everyone else keeps the fare exactly as they have it today. This is a narrowing for one
profile, not a change to the feature.

**The consequence, said plainly so it is a decision and not a surprise:** when Chaman
creates a brand new route, that route starts with no fare on it, and somebody, meaning
Sonu, has to set it before it can be charged for. That is arguably correct, since the fare
is his. But it means a route can exist for a while with no price on it. If you would rather
Chaman could not create a route at all, only change the ones that exist, say so and I will
build it that way instead.

---

## Part 2: the screens I propose he holds

He holds six today, none of which he can reach, because he has no login and no write
ability.

| Screen | Today | Proposed | Why |
|---|---|---|---|
| Transport | yes | **yes, with the fare removed** | His job. See Part 1. |
| Route Optimisation | yes | **yes** | Address lookup, nearest-route suggestion, clustering. Already built, already tested for his profile, carries no money. |
| Student Database | yes | **yes, narrowed** | See Part 3. |
| Asset Tracker | yes | **yes** | The vehicle and equipment register. Carries no money. |
| Custom Forms | yes | **yes** | Any employee has this. |
| Report a problem | yes | **yes** | Answer 1 of the draft: he reports a problem with a bus or with school property. |
| **Maintenance Schedule** | no | **ADD** | Answer 2. He arranges the servicing, so he needs to see and set when it is due. Checked: this record holds a title, a date, a recurrence, a category, who it is assigned to and which contractor. **No money field exists on it at all.** |
| **Vendor Log** | no | **ADD, read only** | Answer 2, the contractors' phone numbers. Checked: a contractor record holds a name, a category, a contact person, a phone, an email, an address, a GST number and a rating. **No money field exists on it either.** The maintenance person may add contractors by answer 8; Chaman was never given that, so I propose he reads and does not add. |

**Nothing else.** No fees, no attendance, no academics, no staff beyond his own team, no
certificates.

---

## Part 3: the student list, which is the one I am least sure about

The draft says he sees the phone numbers and addresses of **the families on his routes**,
because he has to ring a parent when a bus is late.

What the platform would actually give him is the **whole roll of 1,842 children**, because
Student Database is one screen and it is not sliced by route.

Two ways to go, and this is your call:

1. **Give him the whole list.** Simplest, and he already technically passes the route today.
   But it means the transport head can read every child's home address and both parents'
   numbers, including the roughly 1,500 who never get on a bus.
2. **Give him only children assigned to a route.** Matches the draft exactly. It is real
   work: a filter on the server that his profile cannot turn off, plus the same rule applied
   to the roster and to anything Flo answers.

**I recommend 2**, and I would rather do the work than widen it, but it adds maybe half a
session. Tell me which.

Separately, and either way: the student record shows a **transport monthly fare** on the fee
panel. That has to be off his view for the same reason as Part 1.

---

## Part 4: the Flo tools I propose he gets

His `tool_domains` is empty today, which is why Flo can do nothing for him at all. I am not
proposing to give him a domain, because the four domains are broad and would sweep in far
more than transport. I propose naming the tools one by one, which is exactly how Sonu's
transport grant was written on 10 August.

**Proposed, seven tools:**

| Tool | What he would be able to ask Flo | Read or write |
|---|---|---|
| `get_transport_status` | "which routes are running, who is driving" | read, **with the fare stripped** |
| `create_transport_route` | "add a new route" | write, **without a fare** |
| `update_transport_route` | "change the driver on route 3" | write, **fare refused** |
| `add_transport_vehicle` | "register bus UP81 whatever" | write |
| `get_student_profile` | "which route is this child on" | read, transport section only, already built that way |
| `update_student` | move a child from one route to another | write, **transport fields only** |
| `get_maintenance_schedule` | "what servicing is due this month" | read |

**Deliberately NOT proposed, and why each:**

- **`delete_transport_route`.** Deleting a route is not the same as reassigning a child, and
  it is already blocked while children are on it. Ask Sonu or Adesh. If you want him to have
  it, say so.
- **Anything that adds or edits a contractor.** Answer 8 gave that to the maintenance
  person, not to him.
- **Every fee, salary, expense, attendance and academic tool.** Not his job, and most are
  money.

**`update_student` is the one that needs the most care**, because it is the tool that lets
him move a child between routes, which answer 1 explicitly gives him. Today that tool can
change a great deal about a child. There is already a pattern for this in the codebase:
Sonu holds `update_staff` and the service underneath accepts only the salary field from him
and silently drops the rest. **I propose the same shape**: from Chaman's profile,
`update_student` accepts the transport fields and nothing else.

---

## Part 5: a second source of truth sitting exactly where his access lands

The maintenance screens do not use the permission table. They use two hand-written helpers
in `backend/routes/issues.py`, and one of them is wrong:

```
def _can_view_all(user):
    return role == "owner" or (role == "admin" and sub_category in ("principal", None))
```

**An admin with no sub-category at all is treated as the principal.** That is not a
decision anybody made; it is a default that leaked. It governs the maintenance calendar, the
contractor list, the whole issue register and the request history.

**I propose fixing it as part of this**, before granting Chaman anything that sits behind
it, and the fix is to stop admitting `None`. Doing it the other way round means building
his access on top of a hole.

**Two things I found while checking it, which I am reporting rather than quietly fixing:**

1. **`GET /api/issues/facility/{request_id}` has no permission check beyond being signed
   in.** Any account on the platform can read a single repair request by its id, including
   `estimated_cost` and `actual_cost`. That is a live money leak to every profile, not just
   to Chaman. Small, because you need the id, but it is real.
2. **The facility request list prints the estimated cost on screen.** Chaman already holds
   "report a problem", so this is on his path. It has to be off his view.

Neither of these is caused by R3-2. Both are in the way of it.

---

## Part 6: what I expect to turn red, and the rule

Granting a dormant profile real access will move the **pinned per-profile reach counts** in
`test_all_nine_profiles_sweep_r2_13.py`. That is correct here and expected: this release
exists to change Chaman's access on purpose. The count moves and the written reason is this
document. That is the difference between a decided change and an accident.

Narrowing the fare and the maintenance helper may turn other tests red. **If it does, I will
bring each one back to you rather than make it green.** That rule has held through R3-0 and
R3-1a and it holds here.

---

## Part 7: what R3-2 ends with

His account. It was deleted on 2026-08-15 with the six other unused office logins, because
the passwords were never handed out. So this does not resurrect anything: it ends with
creating him fresh on the Add Staff screen, which is owner and principal only as of that
same day and shows the username and the one-time password once. That is R3-4, and it
happens only once everything above is built and proven.

---

## What I need from you before I start

1. **The fare.** Confirm it is removed from his screen, his form, his Flo answers and
   refused by the server. And say whether he may create a route at all, given a route he
   creates starts with no price on it.
2. **The student list.** Whole roll, or only children on a route? I recommend only children
   on a route.
3. **The seven Flo tools.** Approve the list, or strike any of them. In particular, say
   whether he may delete a route.
4. **The maintenance helper fix**, which stops treating an admin with no sub-category as the
   principal. It is a narrowing and it affects more than Chaman.

| Date | Change |
|---|---|
| 2026-08-15 | Written. Nothing built. |
