"""Detect and filter out basement / semi-basement listings.

idealista exposes a floor value that may be a human label (Spanish: "Sótano",
"Semisótano", "Bajo", "Planta 3ª") or a short code in its API:
    st = sótano (basement, -1)   ss = semisótano (semi-basement)
    bj = bajo (ground floor)     en = entreplanta (mezzanine)
We drop only below-ground floors (sótano / semisótano); ground floor is kept.
"""

from __future__ import annotations

import re

# Floor *codes* that mean (semi-)basement — matched exactly, case-insensitive.
_BASEMENT_CODES = {"st", "ss"}

# Free-text mentions of (semi-)basement, accents optional.
_BASEMENT_TEXT_RE = re.compile(r"semi[\s-]*s[oó]tano|s[oó]tano|\bbasement\b", re.IGNORECASE)


def is_basement_floor(floor: object) -> bool:
    """True if a floor value (code or label) denotes a (semi-)basement."""
    if floor is None:
        return False
    text = str(floor).strip().lower()
    if text in _BASEMENT_CODES:
        return True
    return bool(_BASEMENT_TEXT_RE.search(text))


def is_basement(text: object) -> bool:
    """True if free text describes a basement or semi-basement floor."""
    if not text:
        return False
    return bool(_BASEMENT_TEXT_RE.search(str(text)))


def filter_out_basement(listings: list[dict]) -> list[dict]:
    """Drop listings whose floor/title/details indicate a (semi-)basement."""
    kept: list[dict] = []
    for item in listings:
        if is_basement_floor(item.get("floor")):
            continue
        blob = " ".join(
            str(item.get(k) or "") for k in ("title", "details", "description")
        )
        if is_basement(blob):
            continue
        kept.append(item)
    return kept
