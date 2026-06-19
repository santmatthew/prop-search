"""Public-transport travel time via the Google Routes API (computeRoutes).

For each origin (a listing's coordinates) we ask for a TRANSIT route to a single
destination and read back the duration. Results are cached on disk keyed by
``origin|destination``.
"""

from __future__ import annotations

from typing import Optional

import requests

from .cache import JsonCache

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
DEFAULT_CACHE = ".cache/transit.json"


class TransitTimer:
    def __init__(self, api_key: str, cache_path: str = DEFAULT_CACHE):
        self.api_key = api_key
        self.cache = JsonCache(cache_path)

    def minutes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> Optional[float]:
        """Transit duration in minutes from origin to destination, or None."""
        key = f"{origin_lat:.5f},{origin_lng:.5f}|{dest_lat:.5f},{dest_lng:.5f}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached if cached >= 0 else None  # -1 means "known no route"

        body = {
            "origin": _waypoint(origin_lat, origin_lng),
            "destination": _waypoint(dest_lat, dest_lng),
            "travelMode": "TRANSIT",
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration",
        }
        resp = requests.post(ROUTES_URL, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        routes = data.get("routes") or []
        if not routes:
            self.cache.set(key, -1)
            return None

        seconds = _parse_duration(routes[0].get("duration"))
        if seconds is None:
            self.cache.set(key, -1)
            return None

        minutes = round(seconds / 60.0, 1)
        self.cache.set(key, minutes)
        return minutes


def _waypoint(lat: float, lng: float) -> dict:
    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}


def _parse_duration(value) -> Optional[float]:
    """Routes API returns duration as e.g. '1234s'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().rstrip("s")
    try:
        return float(text)
    except ValueError:
        return None


def filter_by_transit(
    listings: list[dict],
    timer: TransitTimer,
    dest_lat: float,
    dest_lng: float,
    max_minutes: float,
) -> list[dict]:
    """Keep listings reachable within ``max_minutes``, annotating ``transit_minutes``."""
    kept: list[dict] = []
    for listing in listings:
        lat, lng = listing.get("lat"), listing.get("lng")
        if lat is None or lng is None:
            continue
        mins = timer.minutes(lat, lng, dest_lat, dest_lng)
        if mins is not None and mins <= max_minutes:
            kept.append({**listing, "transit_minutes": mins})
    return kept
