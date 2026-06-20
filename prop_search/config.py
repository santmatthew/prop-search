"""Configuration: filters and secrets for a property search run.

Values come from (in increasing precedence): built-in defaults -> environment
variables / .env -> CLI arguments. Secrets (API keys) live only in the
environment, never in code or version control.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional at import time
    pass


# Madrid centre = Puerta del Sol (km 0 of Spain's road network).
MADRID_CENTRE_LAT = 40.4168
MADRID_CENTRE_LNG = -3.7038

# Default Apify actor (only idealista needs Apify; fotocasa & redpiso use their
# own free APIs).
IDEALISTA_ACTOR = "dz_omar/idealista-scraper-api"   # DataDome handled internally

DEFAULT_SOURCES = ["idealista", "fotocasa", "redpiso"]


@dataclass
class SearchConfig:
    """All parameters for a single search run."""

    # --- Sources to query (translated into the common Listing structure) ---
    sources: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCES))

    # --- Base filters (mapped to each source's own query) ---
    location: str = "madrid-madrid"  # idealista location slug
    # fotocasa "combinedLocationIds" (opaque). Default = Madrid Capital.
    fotocasa_combined_location: str = "724,14,28,173,0,28079,0,0,0"
    redpiso_province: str = "madrid"  # redpiso province_slug
    redpiso_place: Optional[str] = "madrid"  # redpiso place_slug (city); None = whole province
    operation: str = "venta-viviendas"  # sale of homes
    min_price: int = 250_000
    max_price: int = 380_000
    min_size: int = 70  # m2
    min_bedrooms: int = 2
    exclude_basement: bool = True  # drop basement (-1) and semi-basement floors

    # Manual exclusions. IDs are idealista property codes; areas are matched
    # (accent-insensitive substring) against the listing location.
    exclude_ids: list[str] = field(
        default_factory=lambda: ["110706020"]  # Palacio "penthouse" flagged as a scam
    )
    exclude_areas: list[str] = field(default_factory=lambda: ["lavapies"])

    # --- Geo filters (applied client-side after geocoding) ---
    centre_lat: float = MADRID_CENTRE_LAT
    centre_lng: float = MADRID_CENTRE_LNG
    max_centre_km: float = 6.0

    # --- Transit filter (Google Routes API) ---
    destination: Optional[str] = None  # address or "lat,lng"; required for transit step
    max_transit_minutes: Optional[int] = None

    # --- Run controls ---
    # idealista sorts by relevance, not distance, so to honour the centre-radius
    # filter we fetch the whole result set and filter client-side. The actor
    # caps at however many actually match (~$0.0009/result on the free plan).
    max_listings: int = 1000
    limit: Optional[int] = None  # cap listings processed (testing)
    skip_transit: bool = False
    out_prefix: str = "results"

    # --- Secrets (from environment) ---
    apify_token: Optional[str] = field(default=None, repr=False)
    google_api_key: Optional[str] = field(default=None, repr=False)
    idealista_actor: str = IDEALISTA_ACTOR
    proxy_country: str = "ES"  # idealista geoblocks non-Spanish IPs

    @classmethod
    def from_env(cls) -> "SearchConfig":
        """Build a config with secrets and actor pulled from the environment."""
        return cls(
            apify_token=os.getenv("APIFY_TOKEN"),
            google_api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
            idealista_actor=os.getenv("IDEALISTA_ACTOR", IDEALISTA_ACTOR),
        )

    def validate_for_run(self) -> None:
        """Raise a helpful error if required secrets/args are missing."""
        if "idealista" in self.sources and not self.apify_token:
            raise ValueError(
                "APIFY_TOKEN is not set (needed for idealista). Add it to your .env "
                "(see .env.example), or use --sources fotocasa,redpiso."
            )
        if not self.skip_transit:
            # Geocoding uses free Nominatim; only the transit step needs Google.
            if not self.google_api_key:
                raise ValueError(
                    "GOOGLE_MAPS_API_KEY is not set. Add it to your .env "
                    "(see .env.example), or pass --no-transit."
                )
            if not self.destination:
                raise ValueError(
                    "A --destination is required for the transit filter "
                    "(or pass --no-transit to skip it)."
                )
            if self.max_transit_minutes is None:
                raise ValueError(
                    "--max-minutes is required for the transit filter "
                    "(or pass --no-transit to skip it)."
                )
