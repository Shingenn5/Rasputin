import math
import re

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{20,}",
    r"ghp_[A-Za-z0-9_]{20,}",
    r"AIza[0-9A-Za-z_-]{20,}",
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[^\s]+",
]


def _entropy(text):
    if not text:
        return 0
    counts = {c: text.count(c) for c in set(text)}
    return -sum((n / len(text)) * math.log2(n / len(text)) for n in counts.values())


def validate_web_query(query, max_chars=180):
    q = " ".join(str(query or "").split())
    if not q:
        raise ValueError("empty web query")
    if len(q) > max_chars:
        raise ValueError("web query too long; refusing to send possible file content")
    if "\n" in str(query) or "\r" in str(query):
        raise ValueError("web query cannot contain multiline content")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, q):
            raise ValueError("web query looks like it contains a secret")
    for token in re.findall(r"[A-Za-z0-9_\-+/=]{24,}", q):
        if _entropy(token) > 4.2:
            raise ValueError("web query contains a high-entropy token")
    if len(re.findall(r"[{};<>]", q)) > 4:
        raise ValueError("web query looks like code or raw content")
    return q
