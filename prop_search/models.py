"""The common listing structure that every source translates into.

All sources (idealista, fotocasa, redpiso) produce ``Listing`` objects, and the
whole pipeline (geocode, geo/floor/exclusion filters, transit, dedup, output)
operates on this single shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    source: str                          # "idealista" | "fotocasa" | "redpiso"
    id: Optional[str] = None             # source-native id / property code
    price: Optional[int] = None          # euros
    size_m2: Optional[int] = None
    rooms: Optional[int] = None          # bedrooms
    floor: Optional[str] = None          # raw floor label/code if available
    location: Optional[str] = None       # human-readable address/area
    url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    details: str = ""                    # free text (description) for keyword checks

    # Annotated by the pipeline.
    centre_km: Optional[float] = None
    transit_minutes: Optional[float] = None

    # Populated by dedup when the same property appears on multiple sources.
    also_on: list[str] = field(default_factory=list)
    other_urls: list[str] = field(default_factory=list)

    def all_sources(self) -> list[str]:
        return [self.source, *self.also_on]

    def to_row(self) -> dict:
        """Flat dict for CSV/JSON/HTML output."""
        return {
            "source": self.source,
            "also_on": ", ".join(self.also_on),
            "price": self.price,
            "size_m2": self.size_m2,
            "price_per_m2": (round(self.price / self.size_m2)
                             if self.price and self.size_m2 else None),
            "rooms": self.rooms,
            "floor": self.floor,
            "location": self.location,
            "centre_km": self.centre_km,
            "transit_minutes": self.transit_minutes,
            "lat": self.lat,
            "lng": self.lng,
            "url": self.url,
            "other_urls": ", ".join(self.other_urls),
        }
