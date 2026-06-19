"""Detect and filter out basement / semi-basement listings.

idealista is a Spanish site, so floor descriptions appear in Spanish (e.g.
"Bajo", "Sótano", "Semisótano", "Planta 3ª"). We drop only below-ground floors
(basement = -1 = "sótano", and "semisótano"); ground floor ("bajo") is kept.
"""

from __future__ import annotations

import re

# Match sotano / semisotano with or without accents and separators.
_BASEMENT_RE = re.compile(r"semi[\s-]*s[oó]tano|s[oó]tano|\bbasement\b", re.IGNORECASE)


def is_basement(text: object) -> bool:
    """True if the text describes a basement or semi-basement floor."""
    if not text:
        return False
    return bool(_BASEMENT_RE.search(str(text)))


def filter_out_basement(listings: list[dict]) -> list[dict]:
    """Drop listings whose title/details/floor indicate a (semi-)basement."""
    kept: list[dict] = []
    for item in listings:
        blob = " ".join(
            str(item.get(k) or "")
            for k in ("floor", "title", "details", "description")
        )
        if not is_basement(blob):
            kept.append(item)
    return kept
