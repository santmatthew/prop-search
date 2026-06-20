"""Cross-source de-duplication.

The same physical flat is often listed on several portals (and by several
agencies), with slightly different price/size text and approximate coordinates.
Two listings are treated as the same property when price and size are close and
they are geographically near each other (or share an obvious address).

Listings are processed in source-priority order (see ``sources``), so the
first/richest source becomes the primary and the rest are recorded on it via
``also_on`` / ``other_urls``.
"""

from __future__ import annotations

from .geo import haversine_km
from .models import Listing

PRICE_TOL = 0.03      # 3% price difference
SIZE_TOL_M2 = 3       # +/- 3 m2
NEAR_KM = 0.20        # within 200 m counts as the same spot


def _same_property(a: Listing, b: Listing) -> bool:
    # Price must be present and close.
    if a.price and b.price:
        if abs(a.price - b.price) > PRICE_TOL * max(a.price, b.price):
            return False
    # Size must be present and close.
    if a.size_m2 and b.size_m2 and abs(a.size_m2 - b.size_m2) > SIZE_TOL_M2:
        return False
    # Rooms, when both known, must match.
    if a.rooms and b.rooms and a.rooms != b.rooms:
        return False
    # Geographic proximity is the clincher.
    if None not in (a.lat, a.lng, b.lat, b.lng):
        return haversine_km(a.lat, a.lng, b.lat, b.lng) <= NEAR_KM
    # No coordinates to compare: require price AND size to both be present+close
    # (already checked) to avoid false merges.
    return bool(a.price and b.price and a.size_m2 and b.size_m2)


def dedup(listings: list[Listing]) -> list[Listing]:
    """Merge duplicate listings across sources; return the unique primaries."""
    kept: list[Listing] = []
    for item in listings:
        match = next((k for k in kept if _same_property(k, item)), None)
        if match is None:
            kept.append(item)
            continue
        # Record the duplicate on the primary.
        if item.source not in match.also_on and item.source != match.source:
            match.also_on.append(item.source)
        if item.url and item.url not in match.other_urls and item.url != match.url:
            match.other_urls.append(item.url)
        # Backfill any fields the primary was missing.
        for attr in ("size_m2", "rooms", "floor", "lat", "lng", "location", "details"):
            if not getattr(match, attr) and getattr(item, attr):
                setattr(match, attr, getattr(item, attr))
    return kept
