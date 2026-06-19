"""Geographic helpers: great-circle distance and the centre-distance filter."""

from __future__ import annotations

import math
from typing import Iterable

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two lat/lng points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def filter_by_centre(
    listings: Iterable[dict],
    centre_lat: float,
    centre_lng: float,
    max_km: float,
) -> list[dict]:
    """Keep listings within ``max_km`` of the centre, annotating ``centre_km``.

    Listings without coordinates (``lat``/``lng``) are dropped, since the
    distance cannot be computed.
    """
    kept: list[dict] = []
    for item in listings:
        lat, lng = item.get("lat"), item.get("lng")
        if lat is None or lng is None:
            continue
        dist = haversine_km(centre_lat, centre_lng, lat, lng)
        if dist <= max_km:
            item = {**item, "centre_km": round(dist, 3)}
            kept.append(item)
    return kept
