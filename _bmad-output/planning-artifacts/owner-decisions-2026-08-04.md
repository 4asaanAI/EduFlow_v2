# Decisions taken with Abhimanyu — 2026-08-04

Every one of these was asked in plain English and answered directly in session. This file is
the record; nothing here lives only in a chat transcript.

## First, a correction that affects how everything else is read

**`owner` is a SCHOOL role. It is not Abhimanyu.** He is the founder of the platform; the
school's owner is a different person, and the account is **"Aman Litt"**. Several documents
and questions had addressed him as though he held the `owner` role ("your AI limit is used
up", "only you can print certificates"). Those statements are about a school staff account.
Corrected everywhere on his instruction. Nothing about the permission model changes; only
the words used about it.

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | When does the finished work go live? | **Not yet.** Close every remaining open item first, then deploy the whole lot together in one go. |
| 2 | Third role allowed to print certificates and ID cards | **The accountant.** So: school owner + principal + accountant. |
| 3 | Should a link straight to a screen work in a fresh browser tab? | **Yes, always.** Make the safety check smarter (clear only when a genuinely different person signs in) rather than clearing whenever there is no record. |
| 4 | The firewall rule sitting in watch-only mode | **Leave it watching.** Report what it has actually seen, with real numbers, before proposing a change. |
| 5 | The four abilities nobody has ever tried live (Flo writing files, reading photos, reading scans, uploading from tool screens) | **Test them all properly** before anything goes live. |
| 6 | The school's own address, phone, email, principal | **Already updated by Abhimanyu from theaaryans.in.** To be verified, not assumed. |
| 7 | Branch scoping for expenses and certificates | **Not applicable — there is only ONE branch.** The "multi-branch" wording in the project guide was wrong and is corrected. Branch scoping stays in the code as a guard for a future second branch. |
| 8 | Flo's answer-quality baseline | **Run it, and report the weak answers**, not just a score. |
| 9 | The unused Google Gemini key in the live server settings | **Check whether it is still active.** If it is, keep it as a fallback model. If it is not, remove it from the platform entirely. Remove the misleading `LLM_MODEL` setting either way. |
| 10 | The pile of small tidy-up items | **All of it, in one go.** |
| 11 | Nothing stops a failing test reaching the live site | **Block it automatically.** |
| 12 | Broken usage/health reporting, and Flo's guessed patience timings | **Fix the reporting AND measure the timings** on the school's real connection. |
| 13 | Gaps in the school's real data (missing students, orphan logins, admission fields, leave types) | **Leave all of it for now.** No writes to live school data. |
| 14 | The school owner's exhausted AI usage limit | **Reset it and raise the cap** — the cost per message is now far lower than when that limit was set. |
| 15 | The 26 setup tools no longer offered to Flo in chat | **Keep them trimmed.** They still work on the screens. |
| 16 | The directory merge and click-a-person's-name work | **Include it now, before going live.** Accepted that this delays the deploy, because it is the largest item left. |

## What this makes the remaining plan

Everything above becomes one consolidated round of work, and **the deploy happens once, at
the end, with all of it in**. Decision 16 is the long pole; decision 1 means nothing ships
until it and everything else is done.
