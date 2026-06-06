from __future__ import annotations

import re


SENSITIVE_PATTERNS = [
    re.compile(r"mongodb(?:\+srv)?://[^\s\"']+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|credential)s?\s*[:=]\s*[^\s,\"']+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL),
]


def sanitize_error(message: object) -> str:
    text = str(message)
    if not text:
        return "Request failed."
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    if "[REDACTED]" in redacted:
        return "Request failed with a sanitized upstream error."
    if len(redacted) > 240:
        return f"{redacted[:237]}..."
    return redacted
