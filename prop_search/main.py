"""CLI: search multiple property sources, filter, dedup, and write output.

Example:
    python -m prop_search.main \\
        --destination "Calle de Alcalá 1, Madrid" --max-minutes 30 --limit 50
"""

from __future__ import annotations

import argparse
import sys

from .conditions import filter_out_conditions
from .config import SearchConfig
from .dedup import dedup
from .exclude import apply_exclusions
from .floors import filter_out_basement
from .geo import filter_by_centre
from .geocode import Geocoder, geocode_listings
from .idealista_url import build_search_url
from .output import print_summary, write_results
from .sources import get_sources
from .transit import TransitTimer, filter_by_transit


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Multi-source property search + transit filter")
    p.add_argument("--sources", help="comma-separated sources "
                   "(idealista,fotocasa,redpiso); default all")
    # Base filters
    p.add_argument("--location", help="idealista location slug (default madrid-madrid)")
    p.add_argument("--operation", help="idealista operation slug (default venta-viviendas)")
    p.add_argument("--min-price", type=int, help="minimum price in euros")
    p.add_argument("--max-price", type=int, help="maximum price in euros")
    p.add_argument("--min-size", type=int, help="minimum size in m2")
    p.add_argument("--min-bedrooms", type=int, help="minimum number of bedrooms")
    p.add_argument("--include-basement", action="store_true",
                   help="keep basement / semi-basement listings (off by default)")
    p.add_argument("--exclude-id", action="append", metavar="PROPERTY_CODE",
                   help="idealista property code to exclude (repeatable)")
    p.add_argument("--exclude-area", action="append", metavar="AREA",
                   help="neighborhood/area substring to exclude (repeatable)")
    p.add_argument("--exclude-phrase", action="append", metavar="PHRASE",
                   help="description phrase to exclude, e.g. a non-Madrid town (repeatable)")
    # Geo filters
    p.add_argument("--centre-lat", type=float, help="centre latitude")
    p.add_argument("--centre-lng", type=float, help="centre longitude")
    p.add_argument("--max-centre-km", type=float, help="max distance from centre (km)")
    # Transit filter
    p.add_argument("--destination", help="address or 'lat,lng' to measure transit time to")
    p.add_argument("--max-minutes", type=int, dest="max_transit_minutes",
                   help="max public-transport travel time (minutes)")
    p.add_argument("--no-transit", action="store_true", help="skip the transit-time step")
    # Run controls
    p.add_argument("--max-listings", type=int, help="max listings to request from the scraper")
    p.add_argument("--limit", type=int, help="cap listings processed (for testing)")
    p.add_argument("--out", dest="out_prefix", help="output file prefix (default 'results')")
    p.add_argument("--print-url", action="store_true",
                   help="print the idealista search URL and exit")
    return p


def config_from_args(args: argparse.Namespace) -> SearchConfig:
    config = SearchConfig.from_env()
    overrides = {
        "location": args.location,
        "operation": args.operation,
        "min_price": args.min_price,
        "max_price": args.max_price,
        "exclude_basement": False if args.include_basement else None,
        "min_size": args.min_size,
        "min_bedrooms": args.min_bedrooms,
        "centre_lat": args.centre_lat,
        "centre_lng": args.centre_lng,
        "max_centre_km": args.max_centre_km,
        "destination": args.destination,
        "max_transit_minutes": args.max_transit_minutes,
        "max_listings": args.max_listings,
        "limit": args.limit,
        "out_prefix": args.out_prefix,
        "skip_transit": args.no_transit or None,
    }
    for key, value in overrides.items():
        if value is not None:
            setattr(config, key, value)

    if args.sources:
        config.sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    # Exclusions from the CLI are additive to the configured defaults.
    if args.exclude_id:
        config.exclude_ids = list(config.exclude_ids) + args.exclude_id
    if args.exclude_area:
        config.exclude_areas = list(config.exclude_areas) + args.exclude_area
    if args.exclude_phrase:
        config.exclude_phrases = list(config.exclude_phrases) + args.exclude_phrase
    return config


def _resolve_destination(config: SearchConfig, geocoder: Geocoder) -> tuple[float, float]:
    """Turn the destination (address or 'lat,lng') into coordinates."""
    dest = config.destination.strip()
    if "," in dest:
        a, b = dest.split(",", 1)
        try:
            return float(a), float(b)
        except ValueError:
            pass  # not "lat,lng" -> treat as an address
    coords = geocoder.geocode(dest)
    if not coords:
        raise SystemExit(f"Could not geocode destination: {dest!r}")
    return coords


def _fetch_all(config: SearchConfig) -> list:
    """Fetch from each configured source, translating to common Listings.

    A failure in one source is reported but does not abort the others.
    """
    listings = []
    for source in get_sources(config.sources):
        print(f"Fetching {source.name}...")
        try:
            found = source.fetch(config)
        except Exception as exc:  # one bad source shouldn't kill the run
            print(f"  ! {source.name} failed: {exc}")
            continue
        print(f"  {len(found)} from {source.name}.")
        listings.extend(found)
    return listings


def run(config: SearchConfig) -> list:
    config.validate_for_run()

    listings = _fetch_all(config)
    print(f"{len(listings)} total listing(s) across sources.")

    # Earliest filter: drop undesirable sale/occupancy conditions (bare
    # ownership, sold-with-tenants, squatter-occupied) detected in the text.
    before = len(listings)
    listings, cond_counts = filter_out_conditions(listings)
    if before != len(listings):
        print(f"  {len(listings)} after excluding conditions "
              f"({before - len(listings)} dropped: {cond_counts}).")

    if config.exclude_basement:
        before = len(listings)
        listings = filter_out_basement(listings)
        print(f"  {len(listings)} after excluding basement/semi-basement "
              f"({before - len(listings)} dropped).")

    if config.exclude_ids or config.exclude_areas or config.exclude_phrases:
        before = len(listings)
        listings = apply_exclusions(listings, config.exclude_ids,
                                    config.exclude_areas, config.exclude_phrases)
        print(f"  {len(listings)} after manual exclusions "
              f"({before - len(listings)} dropped: ids={config.exclude_ids}, "
              f"areas={config.exclude_areas}, phrases={config.exclude_phrases}).")

    geocoder = Geocoder()
    listings = geocode_listings(listings, geocoder)

    listings = filter_by_centre(
        listings, config.centre_lat, config.centre_lng, config.max_centre_km
    )
    print(f"  {len(listings)} within {config.max_centre_km} km of centre.")

    before = len(listings)
    listings = dedup(listings)
    print(f"  {len(listings)} after cross-source dedup "
          f"({before - len(listings)} merged).")

    if not config.skip_transit:
        dest_lat, dest_lng = _resolve_destination(config, geocoder)
        timer = TransitTimer(config.google_api_key)
        print(f"Computing transit times to {config.destination!r}...")
        listings = filter_by_transit(
            listings, timer, dest_lat, dest_lng, config.max_transit_minutes
        )
        print(f"  {len(listings)} reachable within {config.max_transit_minutes} min.")

    return listings


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)

    if args.print_url:
        print(build_search_url(config))
        return 0

    try:
        results = run(config)
    except ValueError as exc:  # configuration / validation errors
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    controls = {
        "price_min": config.min_price,
        "price_max": config.max_price,
        "price_default": config.slider_price_default,
        "transit_max": config.max_transit_minutes or 0,
        "transit_default": config.slider_transit_default,
        "centre_max": config.max_centre_km,
        "has_transit": not config.skip_transit,
        "destination": config.destination or "",
    }
    csv_path, json_path, html_path = write_results(results, config.out_prefix, controls)
    print_summary(results)
    print(f"\nWrote {csv_path}, {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
