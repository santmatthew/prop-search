"""idealista source via the dz_omar/idealista-scraper-api Apify actor.

The actor handles DataDome internally (auto residential proxy on the free plan),
returns coordinates, and accepts idealista search URLs.
"""

from __future__ import annotations

import json
import os
from typing import Iterable, Optional

from ..idealista_url import build_search_url
from ..models import Listing
from ..parsing import first, parse_price, parse_rooms, parse_size
from .base import Source

# Raw actor items are cached here so a later run can reuse idealista data when the
# Apify actor is unavailable (e.g. monthly usage limit hit). fotocasa/redpiso use
# free APIs and don't need this.
RAW_CACHE = ".cache/idealista_raw.json"


class IdealistaSource(Source):
    name = "idealista"

    def fetch(self, config) -> list[Listing]:
        search_url = build_search_url(config)
        try:
            raw_items = list(_run_actor(config, search_url))
            _save_raw(raw_items)
        except Exception as exc:
            if os.path.exists(RAW_CACHE):
                print(f"  (idealista actor unavailable: {exc}; using cached dataset)")
                raw_items = _load_raw()
            else:
                raise

        listings: list[Listing] = []
        for raw in raw_items:
            listings.append(_to_listing(raw))
            if config.limit and len(listings) >= config.limit:
                break
        return listings


def _save_raw(items: list) -> None:
    os.makedirs(os.path.dirname(RAW_CACHE), exist_ok=True)
    tmp = RAW_CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False)
    os.replace(tmp, RAW_CACHE)


def _load_raw() -> list:
    with open(RAW_CACHE, encoding="utf-8") as fh:
        return json.load(fh)


def _coords(item: dict) -> tuple[Optional[float], Optional[float]]:
    lat = first(item, "latitude", "lat")
    lng = first(item, "longitude", "lng", "lon")
    loc = item.get("location")
    if (lat is None or lng is None) and isinstance(loc, dict):
        lat = lat or loc.get("latitude") or loc.get("lat")
        lng = lng or loc.get("longitude") or loc.get("lng")
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
    except (TypeError, ValueError):
        return (None, None)


def _location(item: dict) -> Optional[str]:
    loc = item.get("location")
    if isinstance(loc, dict):
        return loc.get("name") or loc.get("address")
    parts, seen = [item.get("address"), item.get("neighborhood"),
                   item.get("district"), item.get("municipality")], []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    return ", ".join(seen) or None


def _to_listing(item: dict) -> Listing:
    # Combine the title and description so condition detection (e.g. "nuda
    # propiedad") sees all available text.
    suggested = item.get("suggestedTexts")
    title = suggested.get("title") if isinstance(suggested, dict) else None
    body = first(item, "details", "subtitle", "description") or ""
    details = " ".join(p for p in (title, body) if p)
    lat, lng = _coords(item)
    return Listing(
        source="idealista",
        id=str(first(item, "propertyCode", "id", "adid") or "") or None,
        price=parse_price(first(item, "price", "priceInfo", "amount")),
        size_m2=parse_size(first(item, "size", "surface")) or parse_size(details),
        rooms=parse_rooms(first(item, "rooms", "bedrooms")) or parse_rooms(details),
        floor=first(item, "floor"),
        location=_location(item),
        url=first(item, "url", "link"),
        lat=lat,
        lng=lng,
        details=str(details),
    )


def _run_actor(config, search_url: str) -> Iterable[dict]:
    from apify_client import ApifyClient

    client = ApifyClient(config.apify_token)
    run_input = {
        "Property_urls": [{"url": search_url}],
        "desiredResults": max(config.max_listings, 10),
    }
    run = client.actor(config.idealista_actor).call(run_input=run_input)
    dataset_id = (
        run.get("defaultDatasetId")
        if isinstance(run, dict)
        else getattr(run, "default_dataset_id", None)
    )
    if not dataset_id:
        raise RuntimeError("Apify run returned no dataset id")
    return client.dataset(dataset_id).iterate_items()
