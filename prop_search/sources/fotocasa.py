"""fotocasa.es source via the azzouzana fotocasa-by-search-url Apify actor.

The actor takes a fotocasa search URL and handles anti-bot internally. NOTE:
full Madrid sweeps need a paid Apify plan (the free tier caps runs at ~5
listings); small runs work on the free tier for validation.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..models import Listing
from ..parsing import parse_price, parse_rooms, parse_size
from .base import Source

SITE = "https://www.fotocasa.es"


class FotocasaSource(Source):
    name = "fotocasa"

    def fetch(self, config) -> list[Listing]:
        search_url = build_search_url(config)
        listings: list[Listing] = []
        for raw in _run_actor(config, search_url):
            listings.append(_to_listing(raw))
            if config.limit and len(listings) >= config.limit:
                break
        return listings


def build_search_url(config) -> str:
    params = []
    if config.min_price:
        params.append(f"minPrice={config.min_price}")
    if config.max_price:
        params.append(f"maxPrice={config.max_price}")
    if config.min_size:
        params.append(f"minSurface={config.min_size}")
    if config.min_bedrooms:
        params.append(f"minRooms={config.min_bedrooms}")
    query = ("?" + "&".join(params)) if params else ""
    return f"{SITE}/es/comprar/viviendas/{config.fotocasa_location}/todas-las-zonas/l{query}"


def _get(item: dict, *path, default=None):
    """Nested lookup: _get(item, 'price', 'amount')."""
    cur = item
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _location(item: dict) -> Optional[str]:
    addr = item.get("address") or {}
    parts, seen = [addr.get("neighborhood"), addr.get("municipality"),
                   addr.get("city"), addr.get("province")], []
    for part in parts:
        if part and part not in seen:
            seen.append(str(part))
    return ", ".join(seen) or None


def _coords(item: dict) -> tuple[Optional[float], Optional[float]]:
    lat = _get(item, "coordinates", "latitude")
    lng = _get(item, "coordinates", "longitude")
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
    except (TypeError, ValueError):
        return (None, None)


def _to_listing(item: dict) -> Listing:
    detail = item.get("detailUrl") or ""
    url = detail if detail.startswith("http") else (SITE + detail if detail else None)
    lat, lng = _coords(item)
    return Listing(
        source="fotocasa",
        id=str(item.get("id") or "") or None,
        price=parse_price(_get(item, "price", "amount")),
        size_m2=parse_size(_get(item, "features", "surface")),
        rooms=parse_rooms(_get(item, "features", "rooms")),
        floor=_get(item, "features", "floor"),
        location=_location(item),
        url=url,
        lat=lat,
        lng=lng,
        details=str(item.get("description") or ""),
    )


def _run_actor(config, search_url: str) -> Iterable[dict]:
    from apify_client import ApifyClient

    client = ApifyClient(config.apify_token)
    run_input = {"startUrl": search_url, "maxItems": config.max_listings}
    run = client.actor(config.fotocasa_actor).call(run_input=run_input)
    dataset_id = (
        run.get("defaultDatasetId")
        if isinstance(run, dict)
        else getattr(run, "default_dataset_id", None)
    )
    if not dataset_id:
        raise RuntimeError("Apify run returned no dataset id")
    return client.dataset(dataset_id).iterate_items()
