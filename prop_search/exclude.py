"""Manual exclusions: drop listings by id, by area/neighborhood, or by a phrase
in the description.

Used for one-off removals. Area matching is accent- and case-insensitive
substring matching against the location (so "lavapies" matches
"Lavapiés-Embajadores"). Phrase matching is word-boundary matching against the
description+location — for mis-listed properties whose structured data says
Madrid but whose text reveals another town (e.g. a house "en Turre", Almería).
"""

from __future__ import annotations

import re
import unicodedata


def _norm(text: object) -> str:
    """Lowercase and strip accents for forgiving comparison."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def listing_id(listing) -> str | None:
    """Property code, from the explicit field or the URL."""
    if listing.id:
        return str(listing.id)
    match = re.search(r"/inmueble/(\d+)", listing.url or "")
    return match.group(1) if match else None


def apply_exclusions(
    listings: list,
    exclude_ids: list[str] | None,
    exclude_areas: list[str] | None,
    exclude_phrases: list[str] | None = None,
) -> list:
    """Drop listings matching an excluded id, area, or description phrase."""
    ids = {str(i) for i in (exclude_ids or [])}
    areas = [_norm(a) for a in (exclude_areas or []) if a]
    phrase_res = [re.compile(r"\b" + re.escape(_norm(p)) + r"\b")
                  for p in (exclude_phrases or []) if p]

    kept = []
    for item in listings:
        if listing_id(item) in ids:
            continue
        location = _norm(item.location)
        if any(area in location for area in areas):
            continue
        if phrase_res:
            blob = _norm(f"{item.details} {item.location}")
            if any(pat.search(blob) for pat in phrase_res):
                continue
        kept.append(item)
    return kept
