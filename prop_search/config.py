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

# Default Apify actor: handles DataDome internally (auto residential proxy on
# free plans), no extra keys, returns coordinates. Accepts idealista URLs.
DEFAULT_APIFY_ACTOR = "dz_omar/idealista-scraper-api"


@dataclass
class SearchConfig:
    """All parameters for a single search run."""

    # --- Base idealista filters (applied via the search URL) ---
    location: str = "madrid-madrid"  # idealista location slug
    operation: str = "venta-viviendas"  # sale of homes
    min_price: int = 250_000
    max_price: int = 360_000
    min_size: int = 80  # m2
    min_bedrooms: int = 2
    exclude_basement: bool = True  # drop basement (-1) and semi-basement floors

    # --- Geo filters (applied client-side after geocoding) ---
    centre_lat: float = MADRID_CENTRE_LAT
    centre_lng: float = MADRID_CENTRE_LNG
    max_centre_km: float = 2.5

    # --- Transit filter (Google Routes API) ---
    destination: Optional[str] = None  # address or "lat,lng"; required for transit step
    max_transit_minutes: Optional[int] = None

    # --- Run controls ---
    # idealista sorts by relevance, not distance, so to honour the centre-radius
    # filter we fetch the whole result set and filter client-side. The actor
    # caps at however many actually match (~$0.0009/result on the free plan).
    max_listings: int = 400
    limit: Optional[int] = None  # cap listings processed (testing)
    skip_transit: bool = False
    out_prefix: str = "results"

    # --- Secrets (from environment) ---
    apify_token: Optional[str] = field(default=None, repr=False)
    google_api_key: Optional[str] = field(default=None, repr=False)
    apify_actor: str = DEFAULT_APIFY_ACTOR
    proxy_country: str = "ES"  # idealista geoblocks non-Spanish IPs

    @classmethod
    def from_env(cls) -> "SearchConfig":
        """Build a config with secrets and actor pulled from the environment."""
        return cls(
            apify_token=os.getenv("APIFY_TOKEN"),
            google_api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
            apify_actor=os.getenv("APIFY_ACTOR", DEFAULT_APIFY_ACTOR),
        )

    def validate_for_run(self) -> None:
        """Raise a helpful error if required secrets/args are missing."""
        if not self.apify_token:
            raise ValueError(
                "APIFY_TOKEN is not set. Add it to your .env (see .env.example)."
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
