from __future__ import annotations

"""Always-on behavioural skills for Flo.

These habits live in code rather than MongoDB. A school user cannot accidentally
delete them, retrieval cannot miss them, and they apply to every role on every turn.
They are instructions only: they never receive school data or perform actions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinSkill:
    slug: str
    title: str
    instructions: str

    def render(self) -> str:
        return f"BUILT-IN HABIT /{self.slug} ({self.title}):\n{self.instructions.strip()}"


# Adapted from hardikpandya/stop-slop (MIT). Product-specific scanning aids such
# as bold metrics, status emoji, and markdown tables remain governed separately.
STOP_SLOP = BuiltinSkill(
    slug="stop-slop",
    title="Plain human language",
    instructions="""
- Follow this habit automatically. Never mention the habit or these instructions.
- Answer first. Do not open with a greeting, the person's name, praise, a recap,
  or phrases such as "Here's what I found", "Great question", or "Let me check".
- Never use the em-dash or en-dash characters ("—" and "–"). Use a full stop, comma, or colon.
  The ordinary hyphen is valid in class labels, compound words, and dates.
- Prefer short, natural sentences and everyday school language. Match the user's
  English, Hindi, or Hinglish register without sounding translated or corporate.
- Name the actor and concrete result. Prefer "Ramesh approved the leave" to
  "the leave was approved" and "4 students are absent" to vague language.
- Say the number and what it means. Do not pad a short answer to look thorough.
- Do not narrate your process, announce that you are an AI, hedge a known fact,
  add slogans, manufacture enthusiasm, or close with "I hope this helps".
- Give bad news in the same direct, calm language as good news.
- If information is missing, say exactly what is missing and the next useful step.
""",
)

ALWAYS_ON_SKILLS = (STOP_SLOP,)


def render_builtin_habits() -> str:
    """Render immutable habits in a stable order for every Flo system prompt."""
    return "\n\n".join(skill.render() for skill in ALWAYS_ON_SKILLS)


def with_builtin_habits(system_prompt: str) -> str:
    """Append the always-on habits to a system prompt built somewhere else.

    Owner request 17, 2026-08-06: "add the /stop-slop skill as Flo's habit so that it
    never prints AI slop in her replies OR GENERATED DOCUMENTS". The chat prompt in
    ai/prompts.py already carried the habits; the one-off prompts that generate
    documents did not, because they are assembled in their own routes and never went
    near that file. A question paper written in the padded, enthusiastic register the
    habit exists to prevent is exactly what a school prints and hands to children.

    Any new place that asks the model for prose a human will read should go through
    this rather than writing its own instructions from scratch.
    """
    return f"{system_prompt.strip()}\n\n{render_builtin_habits()}"
