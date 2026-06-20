"""fotocasa.es source via its public gateway API (no auth, no Apify, free).

The fotocasa.es web pages are DataDome-protected, but the frontend's own gateway
``web.gw.fotocasa.es/v2/propertysearch/search`` answers JSON with no auth. We
call it directly and paginate. Locations are addressed by an opaque
``combinedLocationIds`` string (Madrid Capital is the default below).
"""

from __future__ import annotations

import requests

from ..models import Listing
from ..parsing import parse_price, parse_rooms, parse_size
from .base import Source

API_URL = "https://web.gw.fotocasa.es/v2/propertysearch/search"
SITE = "https://www.fotocasa.es"
PAGE_SIZE = 30  # the gateway returns 30 per page
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class FotocasaSource(Source):
    name = "fotocasa"

    def fetch(self, config) -> list[Listing]:
        params = {
            "culture": "es-ES",
            "operationTypeIds": 1,   # buy
            "propertyTypeIds": 2,    # homes / viviendas
            "combinedLocationIds": config.fotocasa_combined_location,
        }
        if config.min_price:
            params["minPrice"] = config.min_price
        if config.max_price:
            params["maxPrice"] = config.max_price
        if config.min_size:
            params["minSurface"] = config.min_size
        if config.min_bedrooms:
            params["minRooms"] = config.min_bedrooms

        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        session = requests.Session()

        listings: list[Listing] = []
        page = 1
        while True:
            params["pageNumber"] = page
            resp = session.get(API_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("realEstates") or []
            if not items:
                break
            for raw in items:
                listings.append(_to_listing(raw))
                if config.limit and len(listings) >= config.limit:
                    return listings
            total = data.get("count") or 0
            if len(listings) >= total or len(listings) >= config.max_listings:
                break
            page += 1
        return listings


def _feature(item: dict, key: str):
    for f in item.get("features", []):
        if f.get("key") == key:
            value = f.get("value")
            return value[0] if isinstance(value, list) and value else value
    return None


def _price(item: dict):
    for tx in item.get("transactions", []):
        if tx.get("transactionTypeId") == 1 and tx.get("value"):
            return tx["value"][0]
    return None


def _location(item: dict) -> str | None:
    """Human-readable location including the neighborhood.

    ``ubication`` is often just the district (e.g. "Centro") when the exact
    street is hidden — the neighborhood ("Embajadores - Lavapiés") lives in
    ``location.upperLevel`` / ``level8``. Include it so area exclusions and
    display work; otherwise e.g. a Lavapiés flat reads only as "Centro".
    """
    addr = item.get("address") or {}
    loc = addr.get("location") or {}
    parts: list[str] = []
    for value in (addr.get("ubication"), loc.get("upperLevel"), loc.get("level8")):
        value = (value or "").strip()
        if value and value not in parts:
            parts.append(value)
    return ", ".join(parts) or None


def _to_listing(item: dict) -> Listing:
    item_addr = item.get("address") or {}
    coords = item_addr.get("coordinates") or {}
    detail = (item.get("detail") or {}).get("es") or ""
    floor = _feature(item, "floor")
    return Listing(
        source="fotocasa",
        id=str(item.get("id") or "") or None,
        price=parse_price(_price(item)),
        size_m2=parse_size(_feature(item, "surface")),
        rooms=parse_rooms(_feature(item, "rooms")),
        floor=str(floor) if floor is not None else None,
        location=_location(item),
        url=(SITE + detail) if detail else None,
        lat=coords.get("latitude"),
        lng=coords.get("longitude"),
        details=str(item.get("description") or ""),
    )
