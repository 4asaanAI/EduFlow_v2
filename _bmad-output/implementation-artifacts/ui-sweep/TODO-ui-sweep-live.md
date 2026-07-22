# UI Sweep — running to-do

Live task list for the Epic 3 + Epic 9 run (branch `ui-sweep-2026-07-22`).
Kept up to date as Abhimanyu adds items mid-run. Anything deferred here also
gets a row in `DEFERRED-AND-DISCOVERIES.md` per rule 6.

Legend: `[x]` done · `[~]` in progress · `[ ]` not started

---

## Epic 9 — Looks Like The Brochure (design foundation)

### 9.1 One place that decides what the platform looks like
- [x] Baloo 2 (display) + Nunito (body); JetBrains Mono kept for code
- [x] Rounder radii, chunky solid-offset shadows, brand blue + orange
- [x] `prefers-reduced-motion` support (the platform had none)
- [x] Single `:focus-visible` ring, both themes
- [x] Committed contrast test — computes ratios, fails the build on a regression
- [x] Light theme retuned (blue-tinted paper) — Abhimanyu: "light mode is alright"
- [x] **Dark theme reverted to neutral grey** — Abhimanyu: "way too much blue"
- [x] Dark surface ladder rebuilt: page dropped to `#141414`, borders raised to
      `#3D3D3D` — cards were 1.15:1 against the page and camouflaged
- [x] `--tool-hex-*` aliases moved onto the ladder so all 25 tool screens follow
- [x] Five light-theme alias gaps closed (dark blocks on a white page)
- [x] Re-verify contrast test against the final grey palette (40 tests green)
- [x] Confirm the logo, header search and cards read clearly in dark

### 9.2 Controls that feel good to press
- [x] `Button` — press is `transform` only, never a layout property
- [x] `Card`, `Pill`, `EmptyState`, `Field`, shared `inputStyle`
- [x] Orange fills carry navy text (white measures 2.65:1 and fails)
- [ ] Tests for the primitives (press state, disabled, testid forwarding)

### 9.3 The shell, and readable text on a phone
- [x] Mobile type scale (UX-DR7) — keyed to viewport width, not `pointer: coarse`
- [x] Layout/Sidebar/Header/modals: 139 hard-coded `isDark ? hex : hex` pairs
      replaced with tokens — this was why the retheme never reached the shell
- [x] Chat composer: focus ring moved to the pill, not the inner field
- [x] "Flo" copied verbatim from `Eduflow-Landing-Page` (markup + animations),
      replacing the sparkle as the assistant's face on the chat greeting
- [x] Fix `project-context.md` "sidebar is 120px fixed" (D-05 closed)
- [ ] Verify at a real 390px phone width

## Epic 3 — Finding One Record Among Two Thousand

### 3.1 Shared sortable table
- [x] `DataTable` — server-side sort, `aria-sort`, keyboard-operable headings
- [x] Wrapper scrolls; the table is never split (D-01 must not return)
- [x] "not recorded" for the fields never captured
- [ ] Tests for sorting, aria-sort and the empty/error split

### 3.2 Rows per page
- [x] 5/10/15/20/25/30, default 15, persisted per table
- [x] Every unusable stored value falls back instead of throwing
- [x] Size sent to the API — server paginates, never a client slice
- [x] Changing size or sort returns to page 1
- [x] Tests (24)

### 3.3 The lists people actually use
- [x] Student list on the shared table
- [x] Server sort whitelists widened; class sort uses the school's real order
- [x] `class_order.py` + 25 tests
- [x] Staff Tracker on the shared table
- [x] Staff table shows `designation` (this had already shipped in an earlier run)
- [ ] Audit log, notifications, fee transactions — convert or record as not done

## Epic close (mandatory gate)
- [x] Full backend suite: **1745 passed, 2 failed (the pinned pair), 14 deselected**
      vs baseline 1720 / 2 / 14 — +25 new, no new failures
- [ ] Frontend tests green
- [ ] Six review passes (code, adversarial, edge case, test review, trace, NFR)
- [ ] `scoped_filter`/`scoped_query` grep audit on touched backend files
- [ ] Hands-on check at phone width — no saves, the dev server points at
      LIVE PRODUCTION
- [ ] Retrospective + the five log docs
- [ ] Commit to `ui-sweep-2026-07-22`

## Raised by Abhimanyu mid-run — DONE
- [x] Tool title appearing twice on every tab. First fix only covered desktop,
      so it survived everywhere he was actually looking. Now removed at every
      width, for every role; the EduFlow wordmark takes the space.
- [x] Header icons (menu, search, bell) off the same midline and different
      sizes — they each had their own box. All three now share one `ICON_BTN`.
- [x] EduFlow logo absent on mobile (the sidebar is a drawer, so its logo is
      hidden until you open the menu). Now in the header at every width.
- [x] Blue ring floating inside the search panel — the same fault as the chat
      composer. The row owns the focus indication; the field opts out.
- [x] Live data: `branch-ald` "Aliganj Branch" deleted (verified 0 references),
      placeholder phone / email / website replaced with the school's real ones,
      principal corrected to `ADESH SINGH` read from the staff records.
- [x] Login screen: Flo at the top, EduFlow wordmark replacing the key icon,
      and the whole screen moved onto design tokens (it was the last surface
      still computing its own colours).
- [x] Dark slate boxes on light backgrounds (reported on Query & Support).
      Root cause: the light theme remapped the NEAR-WHITE hex aliases
      (`f5f5f5`, `fafafa`, `f9f9f9`, `f0f0f0`, `d5d5d5`) to dark text colours,
      but the tool screens use them as the LIGHT half of an
      `isDark ? dark : light` pair — so every card, input and hover fill on
      that branch rendered as a dark slab. Pre-existing; Epic 9 made it more
      visible by making the values blue. The remaps are removed: near-white
      aliases stay near-white in both themes. **One token fix, so it corrects
      all five affected screens and every profile at once** — Query & Support,
      Audit Log, Maintenance Tools, Principal Daily and File Upload.

## Chat background — The Aaryans crest (DONE)
Modelled on the school's own enquiry form, which carries two marks: the chariot
crest large and faint in the middle, and "THE AARYANS" repeated as a fine tile.
Both reproduced — crest on `::before`, tile on `::after` (an inline SVG, so no
network request). Applied to the shared chat component, so it appears once for
every role rather than per profile.
- [x] Crest sized to the band Abhimanyu sketched: `min(88%, 52vh, 640px)`
- [x] Confined to the CHAT PANE only — not the sidebar, not tool screens
- [x] Non-interactive, layered behind all content, hidden in high-contrast mode
- [x] 5% / 8% opacity, low enough that every contrast guarantee still holds

### Three self-inflicted faults worth not repeating
1. **`url()` in a stylesheet pointing at `public/` broke the build.** webpack's
   css-loader resolves image references at BUILD time, so `url('/aaryans-logo.jpg')`
   failed with "Module not found". Fixed by passing the path in as a CSS custom
   property set inline from React — custom property values are not resolved.
   Assets referenced from `public/` must never be named literally in CSS.
2. **A stray comment closed early, TWICE, and broke the production build.**
   Editing a `/* ... */` block by appending after its `*/` left prose parsed as
   a selector. It passed dev (which does not minify) and failed only at
   `craco build` with "Expected a pseudo-class or pseudo-element" — a message
   that names neither the file nor the line. **Run `craco build`, not just the
   dev server, before calling a CSS change done.**
3. **`position: fixed` spread the watermark under the sidebar.** `absolute`
   anchors to the chat pane and keeps the crest equally still, because the
   scrolling element is a child. Reported by Abhimanyu.

## Raised mid-run, still open
- [ ] **D-15 confirmed:** the sidebar still reads "Lucknow, Uttar Pradesh", so a
      `school_settings` record exists in production holding the wrong city.
      Correcting it is a database WRITE and needs Abhimanyu's approval.
- [ ] **D-20:** the `ui-ux-pro-max` skill is installed without its data files or
      search script — only `SKILL.md`. Its checklists were used directly.
