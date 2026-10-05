from __future__ import annotations

import re

PATTERNS = [
    r"ignore (?:all|previous|earlier) instructions",
    r"you are now",
    r"refund all",
    r"reveal (?:the )?system prompt",
    r"disregard your rules",
]

def scan_untrusted(text: str) -> list[str]:
    hits = []
    for pattern in PATTERNS:
        if re.search(pattern, text or "", flags=re.I):
            hits.append(pattern)
    return hits
