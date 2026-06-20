"""Geocode addresses to lat/lng.

Uses the free OpenStreetMap Nominatim service (no API key, no billing). Results
are cached on disk keyed by the query string. Listings from the scraper already
carry coordinates, so in practice this is used mainly for the destination.

Nominatim usage policy: send a descriptive User-Agent and keep to <=1 req/sec.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from .cache import JsonCache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "prop-search/0.1 (idealista property search tool)"
DEFAULT_CACHE = ".cache/geocode.json"

# Reject results no more precise than a whole town/city/region. A vague address
# (e.g. "Madrid") otherwise resolves to the city centroid, which silently looks
# like 0 km from centre and gives a bogus transit origin. We keep street/house/
# neighbourhood-level results and treat coarser ones as a miss.
COARSE_TYPES = {
    "city", "town", "village", "municipality", "county", "state_district",
    "state", "region", "province", "country", "continent", "administrative",
}


def _too_coarse(result: dict) -> bool:
    atype = result.get("addresstype") or result.get("type")
    return atype in COARSE_TYPES


class Geocoder:
    def __init__(self, cache_path: str = DEFAULT_CACHE, min_interval: float = 1.1):
        self.cache = JsonCache(cache_path)
        self.min_interval = min_interval
        self._last_call = 0.0

    def geocode(self, query: str) -> Optional[tuple[float, float]]:
        """Return (lat, lng) for an address/area, or None if not found."""
        if not query:
            return None
        cached = self.cache.get(query)
        if cached is not None:
            return tuple(cached) if cached else None  # [] means "known miss"

        self._throttle()
        params = {"q": query, "format": "json", "limit": 1,
                  "countrycodes": "es", "addressdetails": 1}
        resp = requests.get(
            NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        results = resp.json()

        if not results or _too_coarse(results[0]):
            self.cache.set(query, [])  # remember the miss (incl. city-level fallback)
            return None

        coords = (float(results[0]["lat"]), float(results[0]["lon"]))
        self.cache.set(query, list(coords))
        return coords

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


def _listing_query(listing) -> str:
    """Best available address string for a listing, biased to Madrid, Spain."""
    base = listing.location or ""
    if "madrid" not in base.lower():
        base = f"{base}, Madrid, Spain" if base else "Madrid, Spain"
    elif "spain" not in base.lower() and "españa" not in base.lower():
        base = f"{base}, Spain"
    return base


def geocode_listings(listings: list, geocoder: Geocoder) -> list:
    """Fill in lat/lng (in place) for listings that lack coordinates."""
    for listing in listings:
        if listing.lat is not None and listing.lng is not None:
            continue
        coords = geocoder.geocode(_listing_query(listing))
        if coords:
            listing.lat, listing.lng = coords
    return listings
