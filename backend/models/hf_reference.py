"""Normalize Hugging Face repository references without network access."""

import re
from urllib.parse import urlparse

_HF_REPO_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def normalize_hf_reference(value):
    """Return a canonical Hugging Face model id, or None for non-exact text.

    Accepted references are org/model and model URLs on the trusted
    huggingface.co hosts. Collection/revision suffixes are reduced to the
    model repository because the catalog API addresses model repositories,
    not individual files or revisions.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    explicit_scheme = "://" in raw
    host_url = raw.lower().startswith(("huggingface.co/", "www.huggingface.co/"))
    if explicit_scheme or host_url:
        parsed = urlparse(raw if explicit_scheme else f"https://{raw}")
        if parsed.scheme.lower() not in {"", "http", "https"}:
            return None
        host = (parsed.hostname or "").lower().rstrip(".")
        if host not in {"huggingface.co", "www.huggingface.co"}:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        repo_parts = parts[:2]
        if any(not _HF_REPO_PART.fullmatch(part) for part in repo_parts):
            return None
        if len(parts) == 2:
            return "/".join(repo_parts)
        if parts[2] not in {"tree", "blob"} or len(parts) < 4:
            return None
        return "/".join(repo_parts)

    candidate = raw.strip("/")
    parts = candidate.split("/")
    if len(parts) != 2 or any(not _HF_REPO_PART.fullmatch(part) for part in parts):
        return None
    return "/".join(parts)


def _looks_like_url(value):
    raw = str(value or "").strip()
    if not raw:
        return False
    return "://" in raw or raw.lower().startswith(("huggingface.co/", "www.huggingface.co/"))
