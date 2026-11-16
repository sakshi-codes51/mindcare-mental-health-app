"""Crisis-language detection shared by the chatbot, journal and text analysis.

This is deliberately conservative: it is better to show support resources to
someone who did not need them than to miss someone who did. It is a keyword
safety net, not a clinical risk assessment.
"""
import re

_PATTERNS = [
    r"\bkill(?:ing)? myself\b",
    r"\bsuicid\w*",
    r"\bend(?:ing)? (?:my own life|my life|it all)\b",
    r"\btake my own life\b",
    r"\bwant(?:ed)? to die\b",
    r"\bwish i (?:was|were) (?:dead|never born)\b",
    r"\bbetter off dead\b",
    r"\bno reason to (?:live|go on)\b",
    r"\bdon'?t want to (?:live|be alive|wake up)\b",
    r"\b(?:hurt(?:ing)?|harm(?:ing)?|cut(?:ting)?|injur(?:e|ing)) myself\b",
    r"\bself[- ]?harm\w*",
    r"\bnot worth living\b",
    r"\bcan'?t go on\b",
]
_CRISIS_RE = re.compile("|".join(_PATTERNS), re.IGNORECASE)


def normalise(text: str) -> str:
    return (text or "").replace("’", "'").replace("‘", "'")


def detect_crisis(text: str) -> bool:
    """True if the text contains language suggesting suicide or self-harm."""
    return bool(_CRISIS_RE.search(normalise(text)))
