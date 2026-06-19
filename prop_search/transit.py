"""Public-transport travel time via the Google Routes API (computeRoutes).

For each origin (a listing's coordinates) we ask for a TRANSIT route to a single
destination and read back the duration. Results are cached on disk keyed by
``origin|destination``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from .cache import JsonCache

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
DEFAULT_CACHE = ".cache/transit.json"


def next_weekday_morning(hour: int = 9, minute: int = 0) -> datetime:
    """Next upcoming weekday (Mon-Fri) at HH:MM in Europe/Madrid time.

    Transit schedules are time-of-day dependent, so commute estimates use a
    realistic time rather than 'now'. Used here as the arrival deadline (be at
    work by 9 AM). June is CEST (UTC+2); we use a fixed +02:00 offset.
    """
    madrid = timezone(timedelta(hours=2))
    now = datetime.now(madrid)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:  # Sat=5, Sun=6
        candidate += timedelta(days=1)
    return candidate


class TransitTimer:
    def __init__(
        self,
        api_key: str,
        cache_path: str = DEFAULT_CACHE,
        arrival_time: Optional[datetime] = None,
    ):
        self.api_key = api_key
        self.cache = JsonCache(cache_path)
        # Be at the destination by this time (weekday 09:00 Madrid by default).
        self.arrival_time = arrival_time or next_weekday_morning()

    def minutes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> Optional[float]:
        """Transit duration in minutes from origin to destination, or None."""
        arr = self.arrival_time.astimezone(timezone.utc)
        arr_iso = arr.strftime("%Y-%m-%dT%H:%M:%SZ")
        key = (
            f"{origin_lat:.5f},{origin_lng:.5f}|"
            f"{dest_lat:.5f},{dest_lng:.5f}|arr{arr_iso}"
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached if cached >= 0 else None  # -1 means "known no route"

        body = {
            "origin": _waypoint(origin_lat, origin_lng),
            "destination": _waypoint(dest_lat, dest_lng),
            "travelMode": "TRANSIT",
            "arrivalTime": arr_iso,
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
