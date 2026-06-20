"""Property sources. Each adapter translates a portal into common Listings."""

from __future__ import annotations

from .base import Source
from .fotocasa import FotocasaSource
from .idealista import IdealistaSource
from .redpiso import RedpisoSource

# Order matters: dedup keeps the first source's listing as primary, so list the
# richest/most-reliable source first.
ALL_SOURCES: dict[str, Source] = {
    "idealista": IdealistaSource(),
    "fotocasa": FotocasaSource(),
    "redpiso": RedpisoSource(),
}


def get_sources(names: list[str]) -> list[Source]:
    """Return source adapters for the requested names, in registry order."""
    unknown = [n for n in names if n not in ALL_SOURCES]
    if unknown:
        raise ValueError(
            f"Unknown source(s): {unknown}. Available: {list(ALL_SOURCES)}"
        )
    return [src for name, src in ALL_SOURCES.items() if name in names]
