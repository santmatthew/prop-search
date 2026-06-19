"""Geocode listing addresses to lat/lng via the Google Geocoding API.

Results are cached on disk keyed by the query string, so repeated runs never
re-bill the same address.
"""

from __future__ import annotations

from typing import Optional

import requests

from .cache import JsonCache

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DEFAULT_CACHE = ".cache/geocode.json"


class Geocoder:
    def __init__(self, api_key: str, cache_path: str = DEFAULT_CACHE):
        self.api_key = api_key
        self.cache = JsonCache(cache_path)

    def geocode(self, query: str) -> Optional[tuple[float, float]]:
        """Return (lat, lng) for an address/area, or None if not found."""
        if not query:
            return None
        cached = self.cache.get(query)
        if cached is not None:
            return tuple(cached) if cached else None  # [] means "known miss"

        params = {"address": query, "key": self.api_key, "region": "es"}
        resp = requests.get(GEOCODE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results") or []
        if not results:
            self.cache.set(query, [])  # remember the miss
            return None

        loc = results[0]["geometry"]["location"]
        coords = (loc["lat"], loc["lng"])
        self.cache.set(query, list(coords))
        return coords


def _listing_query(listing: dict) -> str:
    """Best available address string for a listing, biased to Madrid, Spain."""
    parts = [p for p in (listing.get("title"), listing.get("location")) if p]
    base = ", ".join(parts) if parts else ""
    if "madrid" not in base.lower():
        base = f"{base}, Madrid, Spain" if base else "Madrid, Spain"
    elif "spain" not in base.lower() and "españa" not in base.lower():
        base = f"{base}, Spain"
    return base


def geocode_listings(listings: list[dict], geocoder: Geocoder) -> list[dict]:
    """Fill in lat/lng for listings that lack coordinates."""
    out: list[dict] = []
    for listing in listings:
        if listing.get("lat") is not None and listing.get("lng") is not None:
            out.append(listing)
            continue
        coords = geocoder.geocode(_listing_query(listing))
        if coords:
            listing = {**listing, "lat": coords[0], "lng": coords[1]}
        out.append(listing)
    return out
