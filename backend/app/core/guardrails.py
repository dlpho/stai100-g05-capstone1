"""
WeatherTato — Input Safety & Guardrails Utilities
"""
import re

EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE_REGEX = r"(?!\b\d{4}[- ]\d{2}[- ]\d{2}\b)(?!\b\d{2}[- ]\d{2}[- ]\d{4}\b)(\+?\d[\d -]{8,}\d)"
CREDIT_CARD_REGEX = r"\b(?:\d[ -]*?){13,16}\b"
NAME_REGEX = r"(?i)\b(?:my\s+name\s+is|i\s+am\s+named|i'm\s+named|this\s+is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"

INJECTION_PATTERNS = [
    "ignore previous", "system prompt", "act as", "jailbreak", "bypass", "override",
    "disregard", "forget all", "forget previous", "new instructions", "you are now",
    "do not follow", "developer mode", "dan", "hypothetical", "pretend", "roleplay",
    "base prompt", "core instructions", "unrestricted", "rule", "forbidden"
]
WEATHER_KEYWORDS = [
    "weather", "forecast", "temperature", "rain", "humidity", "wind", "storm", "typhoon",
    "heat", "climate", "uv", "visibility", "pressure", "el nino", "la nina",
    "precipitation", "sunshine", "evapotranspiration", "soil moisture", "soil temperature",
    "vapour pressure", "wind speed", "wind direction", "wind gust", "cold", "hot", "warm",
    "cool", "drizzle", "shower", "dry", "wet"
]

FARMING_ADVICE_KEYWORDS = [
    "what to plant", "when to plant", "should i plant", "plant corn", 
    "crop recommendation", "fertilizer", "pesticide", "harvesting schedule", 
    "crop yield", "farming advice", "plant "
]


def remove_pii(text: str) -> str:
    """Remove personally identifiable information from a text string."""
    text = re.sub(EMAIL_REGEX, "[REDACTED]", text)
    text = re.sub(PHONE_REGEX, "[REDACTED]", text)
    text = re.sub(CREDIT_CARD_REGEX, "[REDACTED]", text)
    text = re.sub(NAME_REGEX, r"[REDACTED]", text)
    return text


def detect_prompt_injection(text: str) -> bool:
    """Detect whether text contains known prompt injection or jailbreak patterns."""
    lower_text = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower_text:
            return True
    return False


def is_weather_related(text: str) -> bool:
    """Check whether text contains at least one weather-related keyword."""
    lower_text = text.lower()
    for word in WEATHER_KEYWORDS:
        if word in lower_text:
            return True
    return False


def requests_farming_advice(text: str) -> bool:
    """Check whether text requests agronomic or farming advice."""
    lower_text = text.lower()
    for word in FARMING_ADVICE_KEYWORDS:
        if word in lower_text:
            return True
    return False
