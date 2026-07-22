# Epics 3 + 9 — Quality Gate

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

> ## ⚠️ How this gate differed from Epics 1 and 8 — read before trusting it
>
> Epic 1 ran its review lenses as a discrete pass at the end, over a finished
> diff. This run could not: Abhimanyu was testing the app live throughout and
> reporting defects as they appeared, so the diff never sat still.
>
> **What that means honestly:** the six review lenses were applied continuously
> against a moving target rather than once against a frozen one. Findings below
> are real and each was fixed, but I cannot claim the same *systematic sweep*
> Epic 1 got. Anything the owner did not happen to look at got less scrutiny
> than it would have under the Epic 1 process.
>
> **The single most useful signal in this run was not a review lens — it was
> Abhimanyu using the product.** Eleven of the fifteen findings below came from
> him, not from me. That is worth carrying forward, and it is also an
> indictment: most of them were things I could have caught.

---

## Findings

Severity: **H** breaks something for a user · **M** degrades quality ·
**L** hygiene.

| # | Sev | Found by | Issue | Fix | Guarded by |
|---|---|---|---|---|---|
| F-1 | H | contrast test | White on brand orange = 2.65:1; on brand blue = 3.34:1. Copying the brochure literally would have failed NFR-A1 on hundreds of buttons. | Orange fills take navy text; blue fill deepened. | `designTokens.contrast.test.js` |
| F-2 | H | contrast test | `--color-border-strong` at 2.22:1 while the secondary button's **fill** is only 1.32:1 vs the page — the control was identified almost entirely by a line that failed 1.4.11. | Raised to clear 3:1 in both themes. | same |
| F-3 | H | self | The retheme did not reach the app shell at all: 139 `isDark ? '#hex' : '#hex'` pairs computed colours in JS, so switching theme recoloured text and left surfaces behind. | All replaced with tokens. | `project-context.md` now forbids the pattern |
| F-4 | H | Abhimanyu | Every tool tab printed its title **twice**, in every role. | Removed from the header at all widths; wordmark in its place. | — |
| F-5 | H | Abhimanyu | Dark slate boxes on light backgrounds (Query & Support and four other screens). Light theme remapped the **near-white** hex aliases to dark text colours, but screens use them as the *light* half of a pair. Pre-existing; Epic 9 made it visible. | Near-white aliases stay near-white. One token fix, five screens. | comment in `App.css` |
| F-6 | H | Abhimanyu | "Lucknow" persisted after being reported fixed — the code was corrected, the **stored data** was not. | 4 stored values corrected with approval. | D-15b |
| F-7 | H | build | `url()` in a stylesheet pointing at `public/` fails the webpack build outright. | Path passed in as a CSS custom property at runtime. | comment in `index.css` |
| F-8 | H | build | A comment block closed early — **twice** — leaving prose parsed as a selector. Passed the dev server; failed only at `craco build`. | Fixed. | habit note: run a real build after CSS changes |
| F-9 | M | Abhimanyu | Focus ring drawn *inside* the composer's and search panel's own borders, reading as a stray second outline. | Container owns focus; field opts out. | — |
| F-10 | M | Abhimanyu | Header menu/search/bell on different midlines and sizes — three separate definitions. | One shared `ICON_BTN`. | — |
| F-11 | M | Abhimanyu | EduFlow logo absent on mobile (sidebar is a drawer), then duplicated on desktop once added. | Sidebar on desktop, header on mobile. Exactly one per view. | — |
| F-12 | M | Abhimanyu | Send button and keyboard chips filled with `--color-border-strong`, a **line** colour raised for 3:1 — as a fill it read as a muddy smudge. Four more hover states had the same fault. | Proper tokens; zero border-token fills remain. | — |
| F-13 | M | Abhimanyu | Dark theme: sidebar darker than the page, borders invisible, logo camouflaged. | Sidebar lifted above the page; borders raised; logo brightness+saturation. | — |
| F-14 | M | Abhimanyu | Crest watermark showed as a pale slab in dark (JPEG on a white rectangle) and spread under the sidebar (`position: fixed`). | Hidden in dark; `absolute` confines it to the chat pane. | — |
| F-15 | L | Abhimanyu | Audit log text changed size across a single row (11/11/12/11). | Whole file on the type scale; zero fixed sizes remain. | — |

**Dismissed, with reasons**

| Issue | Why not fixed |
|---|---|
| `branches.branch-ald` location unknown | Deleted rather than guessed. Inventing a location for a real school's branch is fabricating data. |
| Two `LayoutRouting` tests failing | **Verified pre-existing** by stashing all work and running against the untouched tree — they fail identically. Not caused here, not fixed here. |
| ~30 `react-hooks/exhaustive-deps` warnings | D-16. Unrelated; would bury this diff. |
| 7 unannotated `scoped_filter` hits in `staff.py` | D-17. Pre-existing, correct, unannotated. |

---

## Gate results

| Check | Result |
|---|---|
| Backend suite | **1745 passed / 2 failed / 14 deselected** — baseline 1720/2/14. The 2 are the pinned pair (D-03). |
| New frontend tests | 102 passing across 4 suites |
| Production build | compiles; warnings pre-existing |
| `scoped_filter` audit | 1 new hit, annotated `# branch-scope: intentional`. Others pre-existing (D-17). |
| Python 3.9 | `class_order.py` has `from __future__ import annotations` |
| No TypeScript | confirmed — `.js` only |
| Hands-on verification | **Done by Abhimanyu, not by me.** He took this over explicitly; Part A of `HUMAN-VERIFICATION-CHECKLIST.md` was written at his request. |

## AC traceability

| AC | Test |
|---|---|
| 3.1 server-side sort | `DataTable.test.js` — "asks the caller to re-sort", "renders rows in the order given" |
| 3.1 `aria-sort` | "marks the active column…", ascending + descending + non-sortable |
| 3.1 heading is a button | "makes each sortable heading a real, keyboard-reachable button" |
| 3.1 "not recorded" | `cellValue` cases incl. a legitimate `0` |
| 3.1 one table, wrapper scrolls | "keeps a single table…", "scrolls the wrapper, not the table" |
| 3.2 sizes + default 15 | `useTablePrefs.test.js` |
| 3.2 corrupt stored value | 8 parametrised cases + storage throwing |
| 3.2 keyed per table | "sizing one table does not resize another" |
| 3.2 server paginates | page count computed from chosen size |
| 3.3 class order | `test_class_order.py` — 25 |
| 9.1 contrast, both themes | `designTokens.contrast.test.js` — 40 |
| 9.2 transform-only press | `primitives.test.js` |
| 9.2 orange keeps navy text | `primitives.test.js` VARIANTS assertions |
| 9.2 disabled is more than colour | `primitives.test.js` |
| **9.3 mobile type scale** | **NOT covered by an automated test** — CSS media queries are not exercised in jsdom. On the human checklist. |
| **3.2 preference survives sign-out** | partially: remount is tested, a real session is not. On the human checklist. |
