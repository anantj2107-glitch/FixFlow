"""Small, explainable normalization for maintenance reports.

This module does not translate text or claim semantic understanding. It reduces
common Hinglish spelling variation before lexical matching or embeddings.
"""

import re
import unicodedata

_REPLACEMENTS = (
    (r"\b(paani|pani)\b", "water"),
    (r"\b(tapak(?:na| raha hai| raha| rha hai)?|leak(?:ing)?)\b", "leak"),
    (r"\b(washroom|restroom)\b", "bathroom"),
    (r"\b(basin)\b", "sink"),
    (r"\b(neeche|niche)\b", "under"),
    (r"\b(kharab|band)\b", "not working"),
    (r"\b(bijli)\b", "electricity"),
    (r"\b(lift)\b", "elevator"),
    (r"\b(kamra)\b", "room"),
    # Common transliterated connectors add little issue meaning. Negation is
    # intentionally not removed, so "not working" remains distinguishable.
    (r"\b(ke|se|ko|hai|ho|raha|rha)\b", ""),
)
_WHITESPACE = re.compile(r"\s+")


def _strip_punctuation(text: str) -> str:
    """Remove punctuation while retaining Unicode letters and combining marks."""
    return "".join(" " if unicodedata.category(character).startswith("P") else character for character in text)


def normalize_ticket_text(value: object) -> str:
    """Return stable text for matching. Empty/non-string input becomes empty."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    text = _strip_punctuation(text)
    for pattern, replacement in _REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return _WHITESPACE.sub(" ", text).strip()
