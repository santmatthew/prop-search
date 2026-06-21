"""redpiso.es source via its internal Nuxt JSON API (no off-the-shelf scraper).

redpiso.es is a Cloudflare-fronted Nuxt 3 app whose frontend calls
``/api/properties`` with clean query params. We call that endpoint directly and
paginate. The list response has no coordinates, so listings are geocoded later
by the pipeline (Nominatim) from their address.
"""

from __future__ import annotations

import re

import requests

from ..cache import JsonCache
from ..models import Listing
from ..parsing import first
from .base import Source

API_URL = "https://www.redpiso.es/api/properties"
DETAIL_BASE = "https://www.redpiso.es/inmueble"
DETAIL_CACHE = ".cache/redpiso_detail.json"
PAGE_SIZE = 50
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class RedpisoSource(Source):
    name = "redpiso"

    def fetch(self, config) -> list[Listing]:
        params = {
            "type": "sale",
            "statuses": ["ongoing", "pending_signature"],
            "sort": "recent",
            "province_slug": config.redpiso_province,
            "property_group_slug": "viviendas",
            "page_size": PAGE_SIZE,
        }
        if config.redpiso_place:
            params["place_slug"] = config.redpiso_place
        if config.min_price:
            params["price_from"] = config.min_price
        if config.max_price:
            params["price_to"] = config.max_price
        if config.min_size:
            params["meters_min"] = config.min_size
        if config.min_bedrooms:
            params["bedrooms_min"] = config.min_bedrooms

        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        session = requests.Session()
        detail_cache = JsonCache(DETAIL_CACHE)

        listings: list[Listing] = []
        page = 1
        while True:
            params["page"] = page
            resp = session.get(API_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items") or []
            if not items:
                break
            for raw in items:
                listing = _to_listing(raw)
                # The list API has no usable description; the long description
                # (needed for condition filters: alquilado/ocupado/nuda) lives in
                # the per-property detail API. Fetch it (cached) and fold in.
                long_desc = _long_description(session, headers, listing.id, detail_cache)
                if long_desc:
                    listing.details = f"{listing.details} {long_desc}".strip()
                listings.append(listing)
                if config.limit and len(listings) >= config.limit:
                    return listings
            total = data.get("total") or 0
            if len(listings) >= total or len(listings) >= config.max_listings:
                break
            page += 1
        return listings


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _long_description(session, headers, code, cache: JsonCache) -> str:
    """Fetch a property's long description from the detail API (cached by code)."""
    if not code:
        return ""
    hit = cache.get(code)
    if hit is not None:
        return hit
    try:
        resp = session.get(f"{API_URL}/{code}", headers=headers, timeout=30)
        resp.raise_for_status()
        prop = (resp.json() or {}).get("property") or {}
        text = _strip_html(prop.get("long_description") or "")
        cache.set(code, text)  # cache successful fetches; let failures retry
        return text
    except Exception:
        return ""


def _location(item: dict) -> str | None:
    """Build a precise, geocodable address from redpiso's structured location.

    ``display_location`` is often too vague (e.g. just "Madrid"), which geocodes
    to the city centroid. The structured ``location`` object carries the street,
    quarter and district, which pin the address to the right place.
    """
    loc = item.get("location") or {}
    parts: list[str] = []

    street = loc.get("street") or {}
    if street.get("name"):
        road = ((street.get("road_type") or {}).get("name") or "").strip()
        line = f"{road} {street['name']}".strip()
        if loc.get("number"):
            line += f", {loc['number']}"
        parts.append(line)

    for key in ("quarter", "district", "place"):
        name = (loc.get(key) or {}).get("name")
        if name and name not in parts:
            parts.append(name)

    return ", ".join(parts) or item.get("display_location")


def _to_listing(item: dict) -> Listing:
    cadastre = item.get("cadastre_property_summary") or {}
    slug = item.get("slug")
    url = f"{DETAIL_BASE}/{slug}" if slug else None
    return Listing(
        source="redpiso",
        id=str(first(item, "code", "id_customer_sale") or "") or None,
        price=item.get("price"),
        size_m2=cadastre.get("meters") or cadastre.get("usable_meters"),
        rooms=cadastre.get("bedrooms"),
        floor=None,  # not in list API; basement detected from description text
        location=_location(item),
        url=url,
        lat=None,
        lng=None,
        details=" ".join(str(item.get(k) or "")
                         for k in ("final_emblem", "short_description")).strip(),
    )
