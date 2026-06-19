"""Build idealista search URLs from base filters.

idealista encodes filters as a comma-separated slug segment in the path, e.g.

    https://www.idealista.com/venta-viviendas/madrid-madrid/
        con-precio-hasta_360000,metros-cuadrados-mas-de_80,de-dos-dormitorios/

NOTE: idealista occasionally changes its slug grammar. The slugs below are the
ones in use at time of writing; verify against a live filtered URL if results
look wrong (open idealista, apply the filters in the UI, copy the URL).
"""

from __future__ import annotations

from .config import SearchConfig

BASE = "https://www.idealista.com"

# idealista uses Spanish ordinal slugs for the "minimum bedrooms" filter.
# Anything beyond the mapped values falls back to the highest available bucket.
_BEDROOM_SLUGS = {
    1: "de-un-dormitorio",
    2: "de-dos-dormitorios",
    3: "de-tres-dormitorios",
    4: "de-cuatro-cinco-habitaciones-o-mas",
}


def _bedroom_slug(min_bedrooms: int) -> str | None:
    if min_bedrooms <= 0:
        return None
    return _BEDROOM_SLUGS.get(min_bedrooms, _BEDROOM_SLUGS[max(_BEDROOM_SLUGS)])


def build_search_url(config: SearchConfig) -> str:
    """Return an idealista search URL applying price, size and bedroom filters."""
    filters: list[str] = []

    if config.max_price:
        filters.append(f"con-precio-hasta_{config.max_price}")
    if config.min_size:
        filters.append(f"metros-cuadrados-mas-de_{config.min_size}")

    bedroom = _bedroom_slug(config.min_bedrooms)
    if bedroom:
        filters.append(bedroom)

    path = f"/{config.operation}/{config.location}/"
    if filters:
        path += ",".join(filters) + "/"

    return f"{BASE}{path}"
