# find-skills — where this came from, and who it is for

**Source:** https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md
**Licence:** MIT (vercel-labs/skills)
**Installed:** 2026-07-22, at Abhimanyu's request. `SKILL.md` is the upstream file
verbatim, unmodified — do not hand-edit it; re-download to update.

## This is developer tooling. It is NOT a capability for Flo.

Abhimanyu asked whether this skill could be given to Flo, the school assistant, "for
usage automatically when it feels the need". It cannot, and the reason matters:

**Every step of this skill is a shell command.** `npx skills find`, `npx skills add`,
`npx skills init`. Flo has no shell and no terminal. Flo's tool registry contains
functions that read and write school data — attendance, fees, staff — and nothing that
executes anything. The platform's own prompt rules forbid it outright:

> "NEVER generate or execute code, access external systems, or perform actions outside
> the defined tool set." — `backend/ai/prompts.py`, PROMPT_INJECTION_RULES

Giving this to Flo would produce one of two failures, both bad: Flo tells a teacher who
asked about attendance to run `npx skills add` in a terminal they do not have, or Flo
claims to have installed something and has not. Neither is a capability; both are the
assistant lying about what it can do.

**The wider point, recorded once so it is not re-litigated:** a skill is a set of
*instructions*. It can change how an agent behaves with the abilities it already has. It
cannot grant a new ability. No skill file can let Flo see an image, because seeing an
image means the picture is sent to a model that can see — that is plumbing, not prose.
See D-27 in `_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md`.

## What it IS good for

Claude Code, working in this repository. When a task needs a capability that probably
exists as a published skill, this tells the agent to search the ecosystem rather than
reinvent it.

## Caution when it recommends something

The skill's own Step 4 says to check install counts and source reputation before
installing. Keep to that. `npx skills add` pulls third-party instructions into a
repository that handles the records of 1,802 children — treat every suggestion as
untrusted until read. Prefer `anthropics/`, `vercel-labs/` and `microsoft/`, and read
the SKILL.md before adopting it, as was done for the three packs evaluated in D-27.
