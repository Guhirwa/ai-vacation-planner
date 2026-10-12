"""
input_guardrails.py

Detects obvious prompt-injection attempts in user-supplied text before it
is stored for later retrieval or sent to an LLM.

This is a plain keyword/pattern check, not a machine-learning classifier.
It catches blunt, common injection phrasing (telling the model to ignore
its instructions, reveal its system prompt, and so on). It is not meant to
catch every possible attack, just the obvious ones, with no extra
dependency and no false sense of completeness.
"""

import re

_INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) instructions",
    r"disregard (all |any |the )?(previous|prior|above|earlier) instructions",
    r"forget (all |any |the )?(previous|prior|above|earlier) instructions",
    r"reveal (your |the )?(system prompt|system instructions|hidden instructions)",
    r"\bnew instructions\s*:",
    r"\bsystem prompt\b",
    r"override (your|the) (instructions|rules|guidelines)",
    r"\bjailbreak\b",
    r"<\|?(system|im_start|im_end)\|?>",
]

_COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in _INJECTION_PATTERNS]


class PromptInjectionDetected(ValueError):
    """Raised when user-supplied text matches a known prompt-injection pattern."""

    def __init__(self, matched_pattern: str):
        self.matched_pattern = matched_pattern
        super().__init__(f"Text matched a known prompt-injection pattern: {matched_pattern!r}")


def check_for_injection(text: str) -> None:
    """Raise PromptInjectionDetected if text matches a known injection pattern.

    Args:
        text: User-supplied text to check (a knowledge document, a voice
            transcript, etc.) before it is stored or sent to an LLM.

    Raises:
        PromptInjectionDetected: If any known injection pattern is found.
    """
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            raise PromptInjectionDetected(pattern.pattern)


# Letters (including accented), digits, spaces, and a few punctuation marks
# that show up in real place names ("St. John's", "São Paulo", "food, drinks").
_SEARCH_TERM_PATTERN = re.compile(r"^[^<>{}\[\]\\|`~^;=+*%$#@_]{1,100}$")


class InvalidSearchTerm(ValueError):
    """Raised when a value used to build an external search query is unsafe or malformed."""

    def __init__(self, field_name: str, value: str):
        self.field_name = field_name
        super().__init__(
            f"{field_name!r} contains characters or length not allowed in a search term: {value!r}"
        )


def validate_search_term(value: str, field_name: str = "value") -> None:
    """Raise InvalidSearchTerm if value isn't a reasonable plain search term.

    Used before interpolating caller-supplied text into an external API's
    query string (e.g. a Nominatim place search), so a search term can't
    carry injection characters or be unreasonably long.

    Args:
        value: The text to validate.
        field_name: Name of the field, used only in the error message.

    Raises:
        InvalidSearchTerm: If value is empty, too long, or has disallowed characters.
    """
    if not _SEARCH_TERM_PATTERN.match(value):
        raise InvalidSearchTerm(field_name, value)
