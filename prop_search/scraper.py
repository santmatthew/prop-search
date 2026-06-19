"""Scrape idealista listings via an Apify actor and normalize them.

The default actor (``makework36/idealista-scraper``) accepts idealista search
URLs and returns one record per listing. Field names vary slightly between
actors, so :func:`normalize_listing` is defensive about where each value lives.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from .config import SearchConfig
from .idealista_url import build_search_url


# --- Parsing helpers -------------------------------------------------------

def parse_price(value: Any) -> Optional[int]:
    """Turn '€485,000' / '485.000 €' / 485000 into an int euro amount."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def parse_size(text: Any) -> Optional[int]:
    """Extract square metres from a details string like '90 m² · 3 hab.'."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = re.search(r"(\d[\d.,]*)\s*m", str(text))
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(1))
    return int(digits) if digits else None


def parse_rooms(text: Any) -> Optional[int]:
    """Extract bedroom count from a details string ('3 hab.', '2 bed.')."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = re.search(r"(\d+)\s*(?:hab|dorm|bed|room|habitaci)", str(text), re.I)
    return int(match.group(1)) if match else None


def _first(item: dict, *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _extract_coords(item: dict) -> tuple[Optional[float], Optional[float]]:
    """Pull lat/lng if the actor happens to provide them, else (None, None)."""
    lat = _first(item, "latitude", "lat")
    lng = _first(item, "longitude", "lng", "lon")
    loc = item.get("location")
    if (lat is None or lng is None) and isinstance(loc, dict):
        lat = lat or loc.get("latitude") or loc.get("lat")
        lng = lng or loc.get("longitude") or loc.get("lng")
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
    except (TypeError, ValueError):
        return (None, None)


def normalize_listing(item: dict) -> dict:
    """Map a raw actor record into a stable internal shape."""
    details = _first(item, "details", "subtitle", "description") or ""
    location = item.get("location")
    if isinstance(location, dict):
        location = location.get("name") or location.get("address")

    lat, lng = _extract_coords(item)

    return {
        "title": _first(item, "title", "name"),
        "price": parse_price(_first(item, "price", "priceInfo", "amount")),
        "size_m2": parse_size(_first(item, "size", "surface")) or parse_size(details),
        "rooms": parse_rooms(_first(item, "rooms", "bedrooms")) or parse_rooms(details),
        "floor": _first(item, "floor"),
        "details": details,
        "location": location,
        "url": _first(item, "url", "link"),
        "lat": lat,
        "lng": lng,
    }


# --- Actor invocation ------------------------------------------------------

def _run_actor(config: SearchConfig, search_url: str) -> Iterable[dict]:
    """Run the Apify actor and yield raw dataset items."""
    from apify_client import ApifyClient

    client = ApifyClient(config.apify_token)
    run_input = {
        "searchUrls": [search_url],
        "startUrls": [{"url": search_url}],
        "maxListings": config.max_listings,
        "maxItems": config.max_listings,
        # idealista geoblocks non-Spanish IPs and uses DataDome, so force
        # Spanish residential proxies. Actors that ignore this key are unharmed.
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": config.proxy_country,
        },
    }
    run = client.actor(config.apify_actor).call(run_input=run_input)
    # apify-client >=3 returns a pydantic Run (attr); older returns a dict.
    dataset_id = (
        run.get("defaultDatasetId")
        if isinstance(run, dict)
        else getattr(run, "default_dataset_id", None)
    )
    if not dataset_id:
        raise RuntimeError("Apify run returned no dataset id")
    return client.dataset(dataset_id).iterate_items()


def scrape(config: SearchConfig) -> list[dict]:
    """Scrape and normalize listings for the given config."""
    search_url = build_search_url(config)
    raw_items = _run_actor(config, search_url)

    listings: list[dict] = []
    for raw in raw_items:
        listings.append(normalize_listing(raw))
        if config.limit and len(listings) >= config.limit:
            break
    return listings
