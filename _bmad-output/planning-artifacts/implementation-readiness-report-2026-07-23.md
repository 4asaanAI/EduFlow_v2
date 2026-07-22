---
stepsCompleted: ['step-01-document-discovery', 'step-02-prd-analysis', 'step-03-epic-coverage-validation', 'step-04-ux-alignment', 'step-05-epic-quality-review', 'step-06-final-assessment']
status: 'COMPLETED 2026-07-23 — scoped to Epic 6. Verdict: READY, with seven corrections applied to the epic before implementation.'
assessmentScope: 'EduFlow UI Sweep — Epic 6 "Nothing Gets Lost" (owner items 14 and 16)'
documentsSelected:
  - prd.md
  - architecture.md
  - ux-design-specification.md
  - epics-ui-sweep-2026-07-22.md
  - aaryans-source-of-truth-2026-07-22.md
documentsExcluded:
  - epics-ai-layer-reliability.md, architecture-ai-layer-reliability.md (separate shipped initiative)
  - epics-platform-reliability.md (separate shipped initiative)
---

# Implementation Readiness Assessment Report

**Date:** 2026-07-23
**Project:** eduflow

## Step 1 — Document Discovery

| Type | Whole documents | Sharded |
|---|---|---|
| PRD | `prd.md` (97.3 KB, 2026-07-08) | none |
| Architecture | `architecture.md` (21.4 KB), `architecture-ai-layer-reliability.md` (11.6 KB) | none |
| Epics & Stories | `epics-ui-sweep-2026-07-22.md` (107.6 KB, 2026-07-23), `epics-ai-layer-reliability.md`, `epics-platform-reliability.md` | none |
| UX | `ux-design-specification.md` (71 KB, 2026-07-08) | none |

**Duplicate resolution: none required.** No whole-vs-sharded conflicts. The multiple
architecture and epic files are separate initiatives, not competing versions.

**Governing document for this assessment:** `epics-ui-sweep-2026-07-22.md`, Epic 6, whose
five stories were authored 2026-07-23 immediately before this check.

---

# Steps 2–6 — scoped to Epic 6: Nothing Gets Lost

## Step 2 — PRD Analysis (requirements Epic 6 claims)

| Requirement | Text (abridged) | Epic 6 coverage | Verdict |
|---|---|---|---|
| FR81 | Navigate between all capability areas from a **persistent navigation surface accessible from every screen** | 6.3 (panel footer → All Notifications), 6.5 (sidebar zone header → All Chats) | ✅ covered — both entry points sit in the shell, so neither page needs a per-role nav edit |
| FR82 | Any list over 20 rows supports pagination **and at minimum one column-level sort** | 6.2, 6.3, 6.4, 6.5 | ✅ covered — and this is the requirement the two lists violate today most starkly: neither can be paged at all |
| NFR-A2 | Visible focus state, ≥2px at ≥3:1 | ACs on 6.1, 6.3, 6.5 | ✅ covered |
| NFR-R1 | Writes atomic; no silent partial writes | 6.4 (bulk delete reports deleted vs not-found) | ✅ covered |
| NFR-S2 | No PII in structured log fields | 6.4 (counts and ids only, never a title or message body) | ✅ covered |
| NFR-P1 | API p95 ≤ 500ms | — | 🟠 **NOT covered — see finding Q-2.** Both new list paths add a `count_documents` plus a sorted paged read, and `conversations` carries only a bare `user_id` index |
| UX-DR5 | One shared sortable table | 6.3, 6.5 | ✅ covered — both consume `DataTable`, neither hand-rolls |
| UX-DR6 | Three-way empty state | 6.3 | 🟠 **half covered — see Q-3.** Story 6.3 states it; Story 6.5 does not |
| UX-DR10 | Rows-per-page 5–30, default 15, server-paginated, persisted per table | 6.3, 6.5 | ✅ covered — UX-DR10 names notifications explicitly as an intended consumer |
| UX-DR1, DR4, DR9 | CSS variables only, `data-testid`, visible focus | ACs on every story | ✅ covered as standing constraints |

**One requirement Epic 6 claims is left uncovered by a story: NFR-P1.** Remediated below.

## Step 3 — Epic Coverage Validation

### Owner items

| Owner item | Story | Verdict |
|---|---|---|
| 14 — View all + mark all read | 6.1 (the bell tells the truth), 6.2 (the list can be paged), 6.3 (the All Notifications page) | ✅ |
| 16 — All Chats page | 6.4 (the history can be paged and searched), 6.5 (the All Chats page) | ✅ |

### Deferred-log items belonging to Epic 6

| Item | Story | Verdict |
|---|---|---|
| D-22 — the shell computed its own colours in JS | 6.1 | ✅ closes the `NotificationsPanel` remainder, the one component Epic 9 missed |
| D-24 — ~22 hand-rolled tables still lack sorting | 6.3, 6.5 | 🟡 partial, and must be reported as partial. The Epics 9+3 checklist told the Owner "the notification list has **not** been moved to the new sortable table yet". Epic 6 moves it, and adds the chat list. That is progress on D-24's count, not its closure |
| D-05 / R-3 — `project-context.md` still says "Sidebar width is 120px fixed" | — | 🟡 **still open, see Q-7.** The 2026-07-22 report carried "fix R-3 in-run" as an explicit condition into Epic 4 and it was not done. Two stale facts now, not one |

**No orphaned stories.** Every Epic 6 story traces to an owner item, a deferred-log entry,
or a requirement.

**Product decisions taken by the Owner before story creation:** three, recorded in the epic
under "Owner decisions taken BEFORE any code was written". This satisfies the D-18 rule —
all three change what a person is allowed to do, and all three were answered on 2026-07-23
before a line was written. Two of them are *refusals* (no notification deletion, no
cross-user chat visibility), which is the more useful half: a later reviewer reading the
absence of those features would otherwise read it as an oversight and "fix" it.

## Step 4 — UX Alignment

- **Epic 6 introduces no new visual language.** It consumes `DataTable` (Epic 3),
  `EmptyState`, `Button`, `Pill` (Epic 9) and `useTablePrefs`. This is the intended
  sequencing and the reason Epic 3 built the table before Epics 6 and 7 needed it.
- **The UX specification (2026-07-08) describes the notification panel and its "Mark all
  as read" action (line 1047) but contains neither an All Notifications page nor an All
  Chats page.** The epic document governs; there is no conflict, only silence. R-4 from
  the 2026-07-22 report — that the UX spec is drifting from the built product — is now
  more overdue, since Epic 7 (the next and last epic) contains genuinely new product
  scope and is the one that most needs a current spec.
- **Mobile:** both pages inherit the `DataTable` wrapper-scroll rule, and both stories
  restate D-01 explicitly rather than assuming the shared component protects them.

## Step 5 — Epic Quality Review (autonomous, against create-epics-and-stories standards)

### Epic structure

| Check | Result |
|---|---|
| Epic delivers user value, not a technical milestone | ✅ "every notification and every past conversation is reachable" is an outcome |
| Epic functions independently | ✅ needs only Epic 3's table and Epic 9's primitives, both shipped and deployed |
| No dependency on a *future* epic | ✅ — Epic 7 consumes Epic 3's table too, not Epic 6's pages |
| Traceability to FRs maintained | ✅ (step 2 table) |
| Database entities created only where needed | ✅ no new collection; one new index (once Q-2 is applied) |

### Story-level

| Story | Independently completable | Forward dependency | ACs testable | Sized for one pass |
|---|---|---|---|---|
| 6.1 | ✅ — the bell fix needs only the existing `/unread-count` | none | ✅ | ✅ |
| 6.2 | ✅ | none | ✅ | ✅ |
| 6.3 | ⚠️ needs 6.2 (**backward**, allowed) | none | ✅ | ✅ |
| 6.4 | ✅ | none | ✅ | ✅ |
| 6.5 | ⚠️ needs 6.4 (**backward**, allowed) | none | ✅ | ✅ |

Two backward dependencies, both in the permitted direction. They are ordering constraints,
not violations: implement 6.2 before 6.3 and 6.4 before 6.5. Recorded so the order is not
treated as arbitrary.

### Findings

#### 🔴 Critical

**Q-1 — Two independent counts of "how many are unread", in a story whose own AC forbids
exactly that.** Story 6.1 has the header read `GET /api/notifications/unread-count`. Story
6.2 adds `meta.unread_total` to the list endpoint, with an AC stating the surfaces must be
"three readings of **one** number". As written they are two separately-written queries that
merely happen to agree today. The first time someone adds a filter to one — archived items,
a type exclusion, a date window — the badge and the page disagree, and the symptom is the
one this epic exists to remove: a count you cannot believe.

*Remediation applied:* an AC added to Story 6.2 requiring **one shared count helper**
called by both the `/unread-count` endpoint and the list endpoint's `meta`, with a test that
asserts the two responses agree over the same seeded data.

#### 🟠 Major

**Q-2 — No story mentions an index, and `conversations` has none that serves the new
query.** `database.py:307` creates `conversations.create_index("user_id")` — no `schoolId`,
no `updated_at`. Story 6.4 introduces `count_documents` plus a `sort(updated_at)` paged read
on every load of the sidebar *and* the new page. On a school with a year of conversations
that is an in-memory sort on every screen. `notifications` is already correctly covered by
`(schoolId, user_id, read, created_at desc)` (`database.py:364`), which serves both the
unread filter and either sort direction — so this is a one-collection problem, not two.
The platform rule is that new indexes go in `_create_indexes()` and nowhere else.

*Remediation applied:* an AC added to Story 6.4 requiring
`(schoolId, user_id, updated_at desc)` on `conversations`, added in `_create_indexes()`,
with a note that `notifications` already has what it needs and must not gain a third
duplicate (see Q-6).

**Q-3 — Story 6.5 does not state its empty states, while Story 6.3 does.** The All Chats
page has three distinct empty cases and they mean different things: **no chats at all**
(a new user), **no chats matching your search** (the common one, and the one a bare
"nothing here" would make look like data loss), and **failed to load**. UX-DR6 exists for
precisely this, and an unqualified empty list on a page named "nothing gets lost" is the
worst place in the product to be ambiguous.

*Remediation applied:* the three-way empty state AC added to Story 6.5.

**Q-4 — Story 6.2 does not pin the panel's existing call, while Story 6.4 pins the
sidebar's.** `NotificationsPanel` calls `GET /api/notifications` with no arguments and
must keep receiving exactly what it receives today, digest rows and "All Good" fallback
included. Story 6.4 states this obligation for the sidebar in an explicit AC; Story 6.2
leaves it implicit. Asymmetric rigour is how one of the pair gets a regression test and
the other does not.

*Remediation applied:* the same "no-argument response unchanged, pinned by a test" AC
added to Story 6.2.

**Q-5 — The synthetic rows would be rendered as records on the new page.** `GET
/api/notifications` injects digest rows on page 1 and, when there is nothing at all, a
fabricated "All Good" row. In a dropdown panel that is a sensible empty state. In a
**table of records with a row count, a sort order and a page indicator**, it is an
invented row among real ones — and the "All Good" case would make an empty list look like
a notification saying everything is fine. Story 6.2 excludes both under `unread_only=true`
and says nothing about the ordinary unfiltered case, which is the one the page loads by
default.

*Remediation applied:* Story 6.2 gains an explicit `include_digest` parameter defaulting to
`true` (so the panel is untouched); the All Notifications page passes `false`. One decision
removes the digest rows, the fallback row and the `unread_only` special case together.

**Q-6 — A pre-existing duplicate index, found while checking Q-2.**
`db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])` appears
twice, at `database.py:367` and `database.py:377`, identically. Mongo treats the second as
a no-op, so the cost is confusion rather than storage. Pre-existing, unrelated to this
epic, and touching it would put an unrelated change in an index diff.

*Disposition:* **not fixed. Logged for the deferred register** under rule 6.

#### 🟡 Minor

**Q-7 — `project-context.md` still misinforms every agent, on two facts now.** Line 154
still reads "**Sidebar width is 120px fixed** — all content areas must account for
`margin-left: 120px`", which Epic 9 corrected at line 111 and missed here; the 2026-07-22
report raised it as R-3 and carried "fix in-run" as a condition into Epic 4, where it was
not done. Line 150 additionally still pins the fonts to "`Inter` (body), `JetBrains Mono`"
— superseded by Epic 9 Story 9.1, which explicitly retired UX-DR3 in favour of Baloo 2 and
Nunito. Both are loaded as authoritative by every BMAD workflow.

*Disposition:* **fix in-run**, documentation-only, small and safe, logged under rule 6.
Third time of asking for the first one.

**Q-8 — The destructive confirmation has no stated focus behaviour.** Story 6.5 requires
`role="alertdialog"`, which is right, but the platform's existing modals (the erase-student
dialog in `StudentDatabase.js`) trap nothing and close on nothing. A dialog announced as
an alertdialog that a keyboard user cannot reach or escape is worse than one that is not
announced at all.

*Remediation applied:* AC extended — focus moves into the dialog on open, `Escape` closes
it, and focus returns to the control that opened it.

**Q-9 — Bulk delete leaves the sidebar stale.** Story 6.5 requires that the chat *view* not
point at a deleted conversation, and says nothing about the conversation *list* in the
sidebar, which is on screen at the same time and would keep offering rows that no longer
exist. `Layout` already owns a `convRefresh` counter for exactly this.

*Remediation applied:* AC added to Story 6.5.

**Q-10 — Table ids are unstated.** `useTablePrefs` keys the remembered page size on a
table id, and UX-DR10 requires the preferences be independent. The two new tables must
declare distinct ids that collide with no existing one.

*Remediation applied:* the ids `notifications` and `chats` named explicitly in 6.3 and 6.5,
so a reviewer can check the claim rather than infer it.

## Step 6 — Final Assessment

**Verdict: READY for implementation.**

| Gate | Status |
|---|---|
| Every requirement Epic 6 claims is covered by a story | ✅ after Q-2 |
| Every story has testable, specific acceptance criteria | ✅ |
| No forward dependencies within the epic | ✅ (two backward dependencies, documented) |
| No dependency on an unshipped epic | ✅ |
| Product decisions that change permissions taken by the Owner, before build | ✅ — three, two of them refusals |
| Existing callers of every changed endpoint pinned by a test | ✅ after Q-4 |
| Live-data writes fenced | ⚠️ conditional — see below |

**Conditions carried into implementation:**

1. **Implement 6.2 before 6.3, and 6.4 before 6.5.** The pages cannot honestly satisfy
   their paging ACs against the old endpoints.
2. **Nothing in this epic writes to live data during development.** The dev server proxies
   to production (`setupProxy.js`), so bulk delete must **never** be exercised against the
   running app — it would destroy real conversations. It is verified by test only, and the
   human checklist must say so in as many words.
3. **Fix Q-7 in-run and log it** (third time this condition has been written down).
4. **Log Q-6 in the deferred register** rather than fixing it.
5. The `mark-all-read` request-boundary rule and its test are pre-existing correctness and
   must survive this epic unchanged.
