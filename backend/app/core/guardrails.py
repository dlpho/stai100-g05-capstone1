"""
WeatherTato — Input Safety & Guardrails Utilities
"""
import re

# Regex for simple PII matching, for redaction
EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE_REGEX = r"(?!\b\d{4}[- ]\d{2}[- ]\d{2}\b)(?!\b\d{2}[- ]\d{2}[- ]\d{4}\b)(\+?\d[\d -]{8,}\d)"
NAME_REGEX = r"(?i)\b(?:my\s+name\s+is|i\s+am\s+named|i'm\s+named|this\s+is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"

# Phrase-level prompt injection and jailbreak patterns, for detection
# NOTE: avoid single-word patterns for false positives
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore your instructions",
    "disregard previous instructions",
    "disregard all previous instructions",
    "forget previous instructions",
    "forget all previous instructions",
    "override your instructions",
    "override previous instructions",
    "follow these new instructions",
    "new instructions",
    "system prompt",
    "system message",
    "developer message",
    "developer instructions",
    "reveal your prompt",
    "show your prompt",
    "show me your system prompt",
    "print your instructions",
    "reveal your instructions",
    "bypass your restrictions",
    "bypass your rules",
    "jailbreak",
    "developer mode",
    "unrestricted mode",
    "do not follow your instructions",
    "you are now dan",
    "system override"
]

def remove_pii(text: str) -> str:
    """Remove PII from string."""
    text = re.sub(EMAIL_REGEX, "[REDACTED-EMAIL]", text)
    text = re.sub(PHONE_REGEX, "[REDACTED-PHONE]", text)
    text = re.sub(NAME_REGEX, "[REDACTED-NAME]", text)
    return text


def detect_prompt_injection(text: str) -> bool:
    """Detect whether text contains known prompt injection or jailbreak patterns."""
    # Return True if text matches any injection phrase
    lower_text = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower_text:
            return True
    return False


# def is_weather_related(text: str) -> bool:
#     """Check whether text contains at least one weather-related keyword."""
#     lower_text = text.lower()
#     for word in WEATHER_KEYWORDS:
#         if word in lower_text:
#             return True
#     return False


# def requests_farming_advice(text: str) -> bool:
#     """Check whether text requests agronomic or farming advice."""
#     lower_text = text.lower()
#     for word in FARMING_ADVICE_KEYWORDS:
#         if word in lower_text:
#             return True
#     return False
