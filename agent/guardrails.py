"""Security Guardrails, Prompt Injection Detection, and PII Masking for ExceptionOps.

Hard Rule 1: Risk is enforced in code, not by the prompt.
Hard Rule 2: All shipment notes, customer messages, and tool outputs are untrusted data.
Hard Rule 3: Mask PII (emails, phones) in all outbound customer notifications.
"""

import re
import unicodedata
from typing import Final

EMAIL_REGEX: Final[re.Pattern] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
PHONE_REGEX: Final[re.Pattern] = re.compile(
    r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Heuristic patterns for prompt injection, jailbreaks, and unauthorized override instructions
INJECTION_PATTERNS: Final[list[re.Pattern]] = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?prior\s+instructions", re.IGNORECASE),
    re.compile(r"(?:reveal|output|show|print)\s+(?:your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)?\s*(?:unrestricted|jailbroken|dan|debug|admin)", re.IGNORECASE),
    re.compile(r"system\s+(?:override|alert|prompt)", re.IGNORECASE),
    re.compile(r"admin\s+(?:override|alert|mode)", re.IGNORECASE),
    re.compile(r"bypass\s+(?:all\s+)?(?:security|human|approval)\s*(?:rules|checks|gate)", re.IGNORECASE),
    re.compile(r"auto-approve\s+reroute", re.IGNORECASE),
    re.compile(r"refund\s+(?:the\s+)?customer\s+\$?\d+", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
]

# Authorized transit hubs allowlist
ALLOWED_HUBS: Final[set[str]] = {
    "ORD", "JFK", "LAX", "DFW", "ATL", "MEM",
    "CVG", "MIA", "SEA", "DEN", "BOS", "ANC", "PHX", "OAK"
}


def sanitize_untrusted(text: str) -> str:
    """Sanitize untrusted text by removing non-printable control characters,
    stripping existing delimiter spoofing, and wrapping in strict boundary tags.
    """
    if not text:
        return "<<<UNTRUSTED_CONTENT>>>\n<<<UNTRUSTED_CONTENT>>>"

    # Normalize unicode
    cleaned = unicodedata.normalize("NFKC", text)

    # Strip ASCII control characters except \n, \r, \t
    cleaned = "".join(ch for ch in cleaned if ch in "\n\r\t" or (ord(ch) >= 32 and ord(ch) != 127))

    # Neutralize any attacker attempting to close the delimiter prematurely
    cleaned = cleaned.replace("<<<UNTRUSTED_CONTENT>>>", "[DELIMITER_REMOVED]")

    return f"<<<UNTRUSTED_CONTENT>>>\n{cleaned.strip()}\n<<<UNTRUSTED_CONTENT>>>"


def detect_injection(text: str) -> tuple[bool, str | None]:
    """Inspect text for known prompt injection, override, or jailbreak patterns.
    
    Returns:
        tuple (is_flagged, matched_pattern_text)
    """
    if not text:
        return False, None

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)

    return False, None


def mask_pii(text: str) -> str:
    """Mask email addresses and phone numbers in text."""
    if not text:
        return text
    masked = EMAIL_REGEX.sub("[EMAIL_MASKED]", text)
    masked = PHONE_REGEX.sub("[PHONE_MASKED]", masked)
    return masked


def validate_reroute_hub(hub: str) -> bool:
    """Validate that a hub code exists in the authorized transit hub allowlist."""
    if not hub:
        return False
    return hub.strip().upper() in ALLOWED_HUBS

