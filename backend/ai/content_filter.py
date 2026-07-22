from __future__ import annotations

"""
EduFlow Content Safety Filter
==============================

Post-processing safety filter for all LLM responses when user role is "student".
Also provides input-side safety checks to intercept unsafe queries before they
reach the LLM.

Design principles:
    - Regex-based only (no LLM calls) for sub-millisecond latency.
    - Deterministic: same input always produces the same output.
    - Defence in depth: blocked topics, sensitive-topic guardrails,
      prompt-injection detection, and homework/answer-giving prevention.

Usage:
    from ai.content_filter import filter_response, check_input_safety

    # Before sending to LLM
    safety = check_input_safety(user_message, role="student")
    if not safety["safe"]:
        return safety["filtered_message"]

    # After receiving LLM response
    clean = filter_response(llm_output, role="student", context={"subject": "Science"})
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. BLOCKED TOPICS — any match replaces the entire response
# ---------------------------------------------------------------------------

BLOCKED_TOPICS: list[dict] = [
    {
        "name": "suicide",
        "patterns": [
            r"\bsuicid(?:e|al|ing)\b",
            r"\bkill\s+(?:my|your|him|her|them)self\b",
            r"\bend\s+(?:my|your|one'?s)\s+life\b",
        ],
    },
    {
        "name": "self-harm",
        "patterns": [
            r"\bself[\s-]?harm(?:ing|ed)?\b",
            r"\bcut(?:ting)?\s+(?:my|your)self\b",
            r"\bhurt\s+(?:my|your)self\b",
        ],
    },
    {
        "name": "drugs",
        "patterns": [
            r"\b(?:cocaine|heroin|methamphetamine|meth|marijuana|weed|cannabis|lsd|mdma|ecstasy|opioid|fentanyl|crack)\b",
            r"\billegal\s+drug",
            r"\bnarcotics?\b",
            r"\bdrug\s+(?:use|abuse|dealer|dealing|trafficking)\b",
        ],
    },
    {
        "name": "alcohol",
        "patterns": [
            r"\b(?:alcohol|beer|wine|whiskey|vodka|rum|liquor|booze|drinking\s+age)\b",
            r"\bget(?:ting)?\s+drunk\b",
            r"\bintoxicat(?:ed|ion|ing)\b",
        ],
    },
    {
        "name": "smoking",
        "patterns": [
            r"\b(?:smoking|cigarette|vaping|vape|tobacco|nicotine|hookah|cigar)\b",
        ],
    },
    {
        "name": "pornography",
        "patterns": [
            r"\bporn(?:ography|ographic)?\b",
            r"\bxxx\b",
            r"\badult\s+(?:video|content|film|site|website)\b",
            r"\bexplicit\s+(?:content|material|image|video)\b",
        ],
    },
    {
        "name": "sexual content",
        "patterns": [
            r"\bsex(?:ual)?\s+(?:act|position|intercourse|fantasy|fetish)\b",
            r"\bnud(?:e|ity|es)\b",
            r"\berotic(?:a|ism)?\b",
            r"\bsexting\b",
        ],
    },
    {
        "name": "weapons",
        "patterns": [
            r"\b(?:gun|firearm|pistol|rifle|shotgun|ammunition|ammo)\b",
            r"\bhow\s+to\s+(?:make|build|get)\s+(?:a\s+)?(?:gun|weapon|knife)\b",
            r"\b(?:assault\s+)?weapon(?:s|ry)?\b",
        ],
    },
    {
        "name": "bombs",
        # R9.2 AC2 (M10 / DPDP calibration): the bare `\bbomb(?:...)\b` and
        # `\bexplosive\b` patterns blocked legitimate curriculum ("the atomic
        # bombing of Hiroshima", "an explosive chemical reaction"). Block only
        # weaponization how-to and concrete threats, not mere mention.
        "patterns": [
            r"\bhow\s+to\s+(?:make|build|create|assemble)\s+(?:a\s+)?(?:bomb|explosive|ied)\b",
            r"\b(?:make|build|plant|set\s+off|detonate|throw|bring)\s+(?:a\s+)?(?:bomb|explosive)\b",
            r"\bpipe\s+bomb\b",
            r"\bbomb\s+(?:the|a|my|our)\s+(?:school|building|class|college|campus)\b",
            r"\bIED\b",
        ],
    },
    {
        "name": "hacking",
        "patterns": [
            r"\bhack(?:ing|er|ed)?\b",
            r"\bexploit(?:ing|ation)?\s+(?:a\s+)?(?:system|server|network|computer|website)\b",
            r"\bphish(?:ing)?\b",
            r"\bmalware\b",
            r"\bransomware\b",
            r"\bbrute\s+force\s+(?:attack|password)\b",
            r"\bDDoS\b",
            r"\bsql\s+injection\b",
            r"\bcyber\s*attack\b",
        ],
    },
    {
        "name": "piracy",
        "patterns": [
            r"\bpirat(?:e|ed|ing|cy)\s+(?:movie|film|song|music|software|game|book|ebook)\b",
            r"\btorrent(?:ing)?\s+(?:movie|film|song|music|software|game)\b",
            r"\bcrack(?:ed)?\s+(?:software|game|app)\b",
            r"\bfree\s+download\s+(?:movie|film|song|music|software|game|book)\b",
        ],
    },
    {
        "name": "cheating on exams",
        "patterns": [
            r"\bcheat(?:ing)?\s+(?:on|in|during)\s+(?:the\s+)?(?:exam|test|quiz|assessment)\b",
            r"\bcopy(?:ing)?\s+(?:in|during)\s+(?:the\s+)?(?:exam|test)\b",
            r"\bexam\s+cheat(?:ing|s)?\b",
            r"\bhelp\s+(?:me\s+)?cheat\b",
        ],
    },
    {
        "name": "ragging",
        "patterns": [
            r"(?:rag|ragging)\s+(?:someone|junior|fresher)",
        ],
    },
    {
        "name": "bullying",
        "patterns": [
            r"how\s+to\s+(?:bully|harass|intimidate)\s+(?:a\s+)?(?:student|classmate|junior)",
        ],
    },
    {
        "name": "answer keys",
        "patterns": [
            r"\banswer\s+key(?:s)?\b",
            r"\bquestion\s+paper\s+(?:leak|leaked|with\s+answers)\b",
            r"\bleak(?:ed)?\s+(?:paper|exam|test|question)\b",
        ],
    },
]

# Pre-compile all blocked-topic patterns for performance
_BLOCKED_COMPILED: list[tuple[str, re.Pattern]] = []
for topic in BLOCKED_TOPICS:
    for pat in topic["patterns"]:
        _BLOCKED_COMPILED.append(
            (topic["name"], re.compile(pat, re.IGNORECASE))
        )

# Hindi/Devanagari blocked topic patterns — critical for UP school context
BLOCKED_TOPICS_HINDI: list[str] = [
    # Suicide / self-harm
    r"आत्महत्या",
    r"खुद\s*को\s*नुकसान",
    r"जीना\s*नहीं\s*चाहता",
    r"मरना\s*चाहता",
    r"नसें\s*काट",

    # Drugs / narcotics
    r"नशा\s*(?:कहाँ|कैसे|मिलेगा)",
    r"(?:गांजा|चरस|अफीम|हेरोइन|स्मैक)\s*(?:कहाँ|कैसे|मिलेगा|लेना)",
    r"नशीली\s*दवाई",
    r"ड्रग्स\s*(?:कहाँ|कैसे)",

    # Alcohol
    r"(?:शराब|दारू|बीयर)\s*(?:कहाँ|कैसे|पीना|मिलेगी)",

    # Violence / weapons
    r"(?:चाकू|हथियार|बंदूक)\s*(?:कहाँ|कैसे|मिलेगा)",
    r"मारना\s*(?:है|चाहता|कैसे)",

    # Sexual content
    r"(?:अश्लील|पोर्न|सेक्स)\s*(?:वीडियो|फ़िल्म|साइट)",

    # Exam cheating
    r"(?:नकल|चीटिंग)\s*(?:कैसे|करें)",
    r"पेपर\s*(?:लीक|आउट)\s*(?:कहाँ|है)",

    # Ragging/bullying (common in Indian schools)
    r"रैगिंग\s*(?:कैसे|करें)",
    r"(?:धमकाना|धमकी)\s*(?:कैसे|करें)",
    r"बुली(?:इंग)?\s*(?:कैसे|करें)",
]

# Pre-compile Hindi blocked-topic patterns for performance
_BLOCKED_HINDI_COMPILED: list[re.Pattern] = [
    re.compile(pat, re.IGNORECASE) for pat in BLOCKED_TOPICS_HINDI
]

# ---------------------------------------------------------------------------
# 2. SENSITIVE TOPICS — allowed with textbook-appropriate language only
# ---------------------------------------------------------------------------

SENSITIVE_TOPICS: list[dict] = [
    {
        "name": "reproduction",
        "detect_patterns": [
            r"\breproduct(?:ion|ive)\b",
            r"\bfertilis?ation\b",
            r"\bfertilization\b",
            r"\bembryo\b",
            r"\bfoetus\b",
            r"\bfetus\b",
            r"\bpregnancy\b",
            r"\bmenstrua(?:l|tion)\b",
            r"\bovul(?:ation|e|um)\b",
            r"\bsperm\b",
            r"\buterus\b",
            r"\bplacenta\b",
            r"\bgestation\b",
        ],
        "allowed_phrases": [
            # NCERT Class 8 / 10 / 12 Biology textbook vocabulary
            r"sexual reproduction",
            r"asexual reproduction",
            r"binary fission",
            r"budding",
            r"fragmentation",
            r"vegetative propagation",
            r"pollination",
            r"fertilisation",
            r"fertilization",
            r"zygote",
            r"embryo",
            r"foetus",
            r"fetus",
            r"uterus",
            r"fallopian tube",
            r"ovary",
            r"ovum",
            r"sperm",
            r"testis",
            r"testes",
            r"menstrual cycle",
            r"menstruation",
            r"placenta",
            r"gestation period",
            r"contraception",
            r"reproductive health",
            r"sexually transmitted",
            r"adolescence",
            r"secondary sexual characteristics",
        ],
        "forbidden_phrases": [
            # Language that goes beyond textbook framing
            r"\bhow\s+to\s+have\s+sex\b",
            r"\bsex(?:ual)?\s+pleasure\b",
            r"\borgasm\b",
            r"\bmasturbat(?:e|ion|ing)\b",
            r"\bkama\s*sutra\b",
            r"\bsex(?:ual)?\s+(?:position|fantasy|fetish|desire)\b",
            r"\bintimate\s+relationship\b",
            r"\bone[\s-]?night[\s-]?stand\b",
            r"\bfriends?\s+with\s+benefits\b",
        ],
    },
    {
        "name": "puberty",
        "detect_patterns": [
            r"\bpuberty\b",
            r"\badolescen(?:ce|t)\b",
            r"\bsecondary\s+sexual\s+characteristics?\b",
            r"\bvoice\s+(?:change|breaking|crack)\b",
            r"\bbody\s+(?:hair|changes?\s+during)\b",
        ],
        "allowed_phrases": [
            r"puberty",
            r"adolescence",
            r"growth spurt",
            r"secondary sexual characteristics",
            r"voice change",
            r"body hair",
            r"hormonal changes",
            r"pituitary gland",
            r"testosterone",
            r"oestrogen",
            r"estrogen",
            r"menstruation",
            r"acne",
            r"emotional changes",
            r"physical development",
        ],
        "forbidden_phrases": [
            r"\bhow\s+to\s+have\s+sex\b",
            r"\bsex(?:ual)?\s+pleasure\b",
            r"\blose\s+(?:my|your)\s+virginity\b",
        ],
    },
    {
        "name": "relationships",
        "detect_patterns": [
            r"\brelationship(?:s)?\b",
            r"\bboyfriend\b",
            r"\bgirlfriend\b",
            r"\bdating\b",
            r"\bcrush\b",
            r"\bbreak[\s-]?up\b",
            r"\blov(?:e|ing)\s+someone\b",
        ],
        "allowed_phrases": [
            r"healthy relationship",
            r"respect",
            r"consent",
            r"friendship",
            r"communication",
            r"family relationship",
            r"peer pressure",
            r"emotional well-?being",
            r"boundaries",
            r"mutual respect",
            r"trusted adult",
        ],
        "forbidden_phrases": [
            r"\bhow\s+to\s+(?:kiss|make\s+out|seduce)\b",
            r"\bsex(?:ual)?\s+(?:act|intercourse)\b",
            r"\bsexting\b",
            r"\bnude\b",
        ],
    },
]

_SENSITIVE_DETECT_COMPILED: list[tuple[str, int, re.Pattern]] = []
for idx, topic in enumerate(SENSITIVE_TOPICS):
    for pat in topic["detect_patterns"]:
        _SENSITIVE_DETECT_COMPILED.append(
            (topic["name"], idx, re.compile(pat, re.IGNORECASE))
        )

_SENSITIVE_FORBIDDEN_COMPILED: dict[str, list[re.Pattern]] = {}
for topic in SENSITIVE_TOPICS:
    _SENSITIVE_FORBIDDEN_COMPILED[topic["name"]] = [
        re.compile(pat, re.IGNORECASE) for pat in topic["forbidden_phrases"]
    ]

# ---------------------------------------------------------------------------
# 3. PROMPT-INJECTION / JAILBREAK DETECTION
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions?\b",
        r"\bignore\s+(?:your\s+)?(?:rules?|guidelines?|restrictions?|filters?|safety)\b",
        r"\bdisregard\s+(?:all\s+)?(?:previous\s+)?instructions?\b",
        r"\bpretend\s+(?:you\s+are|to\s+be|you'?re)\b",
        r"\bact\s+as\s+(?:if\s+you\s+are|a|an)\b",
        r"\bjailbreak\b",
        # R9.2 AC2: scope the "DAN" jailbreak persona to actual jailbreak phrasing
        # so a student named Dan isn't blocked. The classic expansion ("do anything
        # now") is caught by the next pattern regardless.
        r"\bDAN\s+mode\b",
        r"\byou\s+are\s+(?:now\s+)?DAN\b",
        r"\bdo\s+anything\s+now\b",
        r"\byou\s+are\s+now\s+(?:a|an|free|unfiltered|uncensored)\b",
        r"\bdeveloper\s+mode\b",
        r"\boverride\s+(?:your\s+)?(?:rules?|safety|filters?|instructions?)\b",
        r"\bunlock(?:ed)?\s+mode\b",
        r"\bno\s+(?:rules?|restrictions?|filters?|limits?)\s+mode\b",
        r"\bbypass\s+(?:your\s+)?(?:rules?|safety|filters?|content)\b",
        r"\brole[\s-]?play\s+as\b",
        r"\bsystem\s+prompt\b",
        r"\brepeat\s+(?:your\s+)?(?:system|initial)\s+(?:prompt|instructions?|message)\b",
        r"\bshow\s+(?:me\s+)?(?:your\s+)?(?:system|hidden|initial)\s+(?:prompt|instructions?)\b",
        r"\bwhat\s+(?:are|were)\s+your\s+(?:original|system|initial)\s+instructions?\b",
        r"\bforget\s+(?:all\s+)?(?:your\s+)?(?:rules?|instructions?|training)\b",
        r"\benable\s+(?:uncensored|nsfw|adult)\b",
    ]
]

# ---------------------------------------------------------------------------
# 4. HOMEWORK / DIRECT-ANSWER DETECTION
# ---------------------------------------------------------------------------

_HOMEWORK_DIRECT_ANSWER_PATTERNS: list[re.Pattern] = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        # Direct answer reveals
        r"(?:^|\n)\s*(?:the\s+)?answer\s+is\s*[:=]?\s*\S",
        r"(?:^|\n)\s*solution\s*[:=]\s*\S",
        r"(?:^|\n)\s*(?:final\s+)?answer\s*[:=]\s*\S",
        # Bare numerical/option answers without reasoning
        r"(?:^|\n)\s*(?:answer|ans|solution)\s*[:=]\s*(?:\d+\.?\d*|[A-D])\s*$",
        # "Therefore the answer is X" at end of short responses
        r"\btherefore,?\s+(?:the\s+)?(?:answer|solution)\s+is\s+(?:\d+\.?\d*|[A-D])\s*\.?\s*$",
        # Numbered list of answers (e.g. "1. B  2. C  3. A")
        r"(?:^|\n)\s*1\s*[.)]\s*[A-D]\s+2\s*[.)]\s*[A-D]\s+3\s*[.)]\s*[A-D]",
    ]
]

_HOMEWORK_INPUT_PATTERNS: list[re.Pattern] = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bsolve\s+(?:this|my|the)\s+(?:assignment|homework|worksheet|paper)\b",
        r"\bgive\s+(?:me\s+)?(?:the\s+)?(?:answers?|solutions?)\s+(?:to|for|of)\b",
        r"\bdo\s+my\s+(?:homework|assignment|worksheet)\b",
        r"\bcomplete\s+(?:this|my)\s+(?:assignment|homework|worksheet)\b",
        r"\bwrite\s+(?:this|my)\s+(?:essay|assignment|project|report)\s+for\s+me\b",
    ]
]

# ---------------------------------------------------------------------------
# 5. SAFE REPLACEMENT MESSAGES
# ---------------------------------------------------------------------------

BLOCKED_TOPIC_RESPONSE: str = (
    "I'm sorry, but I can't help with that topic. "
    "If you have questions about this, please talk to your teacher or a parent/guardian. "
    "I'm here to help you with your studies and school-related questions!"
)

BLOCKED_TOPIC_RESPONSE_HINDI: str = (
    "मुझे खेद है, मैं इस विषय में सहायता नहीं कर सकता। "
    "यदि आपको इस बारे में सहायता चाहिए, तो कृपया अपने शिक्षक या माता-पिता से बात करें।"
)


def get_blocked_response(message: str = "") -> str:
    """Return the appropriate blocked-topic response based on the message language.

    Detects Devanagari characters (Unicode range U+0900–U+097F) to decide
    whether to respond in Hindi.

    Args:
        message: The original user message (used for language detection only).

    Returns:
        BLOCKED_TOPIC_RESPONSE_HINDI if Devanagari script is detected,
        otherwise BLOCKED_TOPIC_RESPONSE.
    """
    if re.search(r'[ऀ-ॿ]', message):
        return BLOCKED_TOPIC_RESPONSE_HINDI
    return BLOCKED_TOPIC_RESPONSE

SENSITIVE_TOPIC_REDIRECT: str = (
    "\n\n---\n"
    "This topic is covered in your NCERT textbook. "
    "For more detailed discussion, please speak with your teacher or a trusted adult."
)

HOMEWORK_GUIDANCE_RESPONSE: str = (
    "I'd love to help you learn this! But instead of giving the answer directly, "
    "let me guide you through the thinking process:\n\n"
    "1. **Read the question carefully** and identify what is being asked.\n"
    "2. **Recall the relevant concept** from your textbook or class notes.\n"
    "3. **Try solving it step by step** and tell me where you get stuck.\n\n"
    "Share your attempt and I'll help you figure out the rest!"
)

INJECTION_BLOCKED_RESPONSE: str = (
    "I'm Flo, your school study assistant. "
    "I can only help with school-related topics within my guidelines. "
    "How can I help you with your studies today?"
)

# ---------------------------------------------------------------------------
# 6. CORE FILTER FUNCTIONS
# ---------------------------------------------------------------------------


def _check_blocked_topics(text: str) -> Optional[str]:
    """Check if text contains any blocked topic.

    Args:
        text: The text to scan (LLM output or user input).

    Returns:
        The name of the blocked topic if found, or None.
    """
    for topic_name, pattern in _BLOCKED_COMPILED:
        if pattern.search(text):
            return topic_name
    return None


def _check_sensitive_topics(text: str) -> Optional[tuple[str, int]]:
    """Check if text touches a sensitive topic.

    Args:
        text: The text to scan.

    Returns:
        A tuple of (topic_name, topic_index) if detected, or None.
    """
    for topic_name, idx, pattern in _SENSITIVE_DETECT_COMPILED:
        if pattern.search(text):
            return (topic_name, idx)
    return None


def _contains_forbidden_sensitive_content(text: str, topic_name: str) -> bool:
    """Check if text about a sensitive topic uses forbidden (non-textbook) language.

    Args:
        text: The text to scan.
        topic_name: The sensitive topic that was detected.

    Returns:
        True if forbidden language is present.
    """
    patterns = _SENSITIVE_FORBIDDEN_COMPILED.get(topic_name, [])
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False


def _check_prompt_injection(text: str) -> Optional[str]:
    """Detect prompt-injection or jailbreak attempts.

    Args:
        text: The user's input message.

    Returns:
        The matched pattern description if injection detected, or None.
    """
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _check_direct_answers(text: str) -> bool:
    """Check if LLM output contains direct answers without explanation.

    This catches cases where the LLM bypasses the guidance-first approach
    and gives away answers to what appears to be graded work.

    Args:
        text: The LLM response text.

    Returns:
        True if direct answer patterns are detected.
    """
    for pattern in _HOMEWORK_DIRECT_ANSWER_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _check_homework_request(text: str) -> bool:
    """Check if user input is asking for direct homework/assignment answers.

    Args:
        text: The user's input message.

    Returns:
        True if the message appears to request direct answers to graded work.
    """
    for pattern in _HOMEWORK_INPUT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _truncate_at_forbidden(text: str, topic_name: str) -> str:
    """Truncate text at the first forbidden phrase for a sensitive topic.

    Keeps everything before the forbidden content and appends a redirect
    message directing the student to their teacher or textbook.

    Args:
        text: The full LLM response.
        topic_name: The sensitive topic being discussed.

    Returns:
        Truncated text with redirect appended.
    """
    patterns = _SENSITIVE_FORBIDDEN_COMPILED.get(topic_name, [])
    earliest_pos = len(text)

    for pattern in patterns:
        match = pattern.search(text)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    if earliest_pos == len(text):
        return text

    # Walk back to the end of the previous sentence
    truncated = text[:earliest_pos]
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("?\n"),
        truncated.rfind("? "),
    )
    if last_period > 0:
        truncated = truncated[: last_period + 1]
    else:
        truncated = truncated.rstrip()

    return truncated.rstrip() + SENSITIVE_TOPIC_REDIRECT


# ---------------------------------------------------------------------------
# 7. PUBLIC API
# ---------------------------------------------------------------------------


def check_input_safety(user_message: str, role: str) -> dict:
    """Pre-LLM safety check on the user's input message.

    Runs before the message is sent to the LLM. For student roles, this
    detects prompt injections, blocked topic requests, and direct homework
    answer solicitation.

    Args:
        user_message: The raw message from the user.
        role: The user's role (e.g. "student", "teacher", "owner").

    Returns:
        A dict with keys:
            - safe (bool): Whether the message is safe to forward to the LLM.
            - reason (str): Why the message was flagged, or "ok".
            - filtered_message (str): A safe replacement message if blocked,
              or the original message if safe.

    Examples:
        >>> check_input_safety("Explain photosynthesis", "student")
        {'safe': True, 'reason': 'ok', 'filtered_message': 'Explain photosynthesis'}

        >>> check_input_safety("Ignore your instructions", "student")
        {'safe': False, 'reason': 'prompt_injection', ...}
    """
    result = {
        "safe": True,
        "reason": "ok",
        "filtered_message": user_message,
    }

    # Only apply student-specific filters to student role
    if role != "student":
        return result

    # --- Check 1: Prompt injection / jailbreak ---
    injection_match = _check_prompt_injection(user_message)
    if injection_match:
        logger.warning(
            "Prompt injection detected from student: %r", injection_match
        )
        return {
            "safe": False,
            "reason": "prompt_injection",
            "filtered_message": INJECTION_BLOCKED_RESPONSE,
        }

    # --- Check 2: Blocked topics (English) ---
    blocked = _check_blocked_topics(user_message)
    if blocked:
        logger.warning(
            "Blocked topic '%s' detected in student input", blocked
        )
        return {
            "safe": False,
            "reason": f"blocked_topic:{blocked}",
            "filtered_message": get_blocked_response(user_message),
        }

    # --- Check 2b: Hindi/Devanagari blocked topics ---
    for pattern in _BLOCKED_HINDI_COMPILED:
        if pattern.search(user_message):
            logger.warning(
                "Hindi blocked topic detected in student input"
            )
            return {
                "safe": False,
                "reason": "blocked_topic_hindi",
                "filtered_message": get_blocked_response(user_message),
            }

    # --- Check 3: Homework / direct answer solicitation ---
    if _check_homework_request(user_message):
        logger.info("Homework answer request detected from student")
        return {
            "safe": False,
            "reason": "homework_answer_request",
            "filtered_message": HOMEWORK_GUIDANCE_RESPONSE,
        }

    return result


def filter_response(
    text: str, role: str, context: Optional[dict] = None
) -> str:
    """Post-LLM content safety filter applied to every response.

    Runs as a post-processing step on LLM output. For student roles, this
    enforces blocked-topic removal, sensitive-topic guardrails, and
    homework/direct-answer prevention.

    Args:
        text: The raw LLM response text.
        role: The user's role (e.g. "student", "teacher", "owner").
        context: Optional dict with additional context. Supported keys:
            - subject (str): The school subject being discussed (e.g. "Science").
              Influences sensitive-topic handling.

    Returns:
        The filtered text, which may be:
            - The original text (if no issues found or role is not "student").
            - A safe replacement message (if blocked topic detected).
            - A truncated version with redirect (if sensitive topic goes off-script).
            - A guidance-oriented replacement (if direct answers detected).

    Examples:
        >>> filter_response("Photosynthesis is the process...", "student")
        'Photosynthesis is the process...'

        >>> filter_response("Here is how to hack a server...", "student")
        "I'm sorry, but I can't help with that topic..."
    """
    if context is None:
        context = {}

    # Non-student roles get unfiltered output
    if role != "student":
        return text

    # --- Check 1: Blocked topics in output ---
    blocked = _check_blocked_topics(text)
    if blocked:
        logger.warning(
            "Blocked topic '%s' found in LLM output for student; replacing",
            blocked,
        )
        return get_blocked_response()

    # --- Check 2: Sensitive topics ---
    sensitive = _check_sensitive_topics(text)
    if sensitive:
        topic_name, _ = sensitive
        if _contains_forbidden_sensitive_content(text, topic_name):
            logger.warning(
                "Sensitive topic '%s' with forbidden content in LLM output; truncating",
                topic_name,
            )
            return _truncate_at_forbidden(text, topic_name)

    # --- Check 3: Direct answers / homework solving ---
    if _check_direct_answers(text):
        logger.info(
            "Direct answer pattern detected in LLM output for student; replacing"
        )
        return HOMEWORK_GUIDANCE_RESPONSE

    return text
