"""Manual exclusions: drop specific listings by id or by area/neighborhood.

Used for one-off removals (e.g. a listing whose description looks like a scam)
and for ruling out neighborhoods. Area matching is accent- and case-insensitive
substring matching against the listing's location text (so "lavapies" matches
"Lavapiés-Embajadores").
"""

from __future__ import annotations

import re
import unicodedata


def _norm(text: object) -> str:
    """Lowercase and strip accents for forgiving comparison."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def listing_id(listing: dict) -> str | None:
    """idealista property code, from the explicit field or the URL."""
    if listing.get("id"):
        return str(listing["id"])
    url = listing.get("url") or ""
    match = re.search(r"/inmueble/(\d+)", url)
    return match.group(1) if match else None


def apply_exclusions(
    listings: list[dict],
    exclude_ids: list[str] | None,
    exclude_areas: list[str] | None,
) -> list[dict]:
    """Drop listings matching an excluded id or area."""
    ids = {str(i) for i in (exclude_ids or [])}
    areas = [_norm(a) for a in (exclude_areas or []) if a]

    kept: list[dict] = []
    for item in listings:
        if listing_id(item) in ids:
            continue
        location = _norm(item.get("location"))
        if any(area in location for area in areas):
            continue
        kept.append(item)
    return kept
