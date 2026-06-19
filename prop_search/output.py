"""Write results to CSV and JSON and print a summary table."""

from __future__ import annotations

import csv
import json
from typing import Optional

FIELDS = [
    "title",
    "price",
    "size_m2",
    "rooms",
    "location",
    "centre_km",
    "transit_minutes",
    "url",
]


def _sort_key(item: dict):
    # Sort by transit time when available, else by distance from centre.
    return (
        item.get("transit_minutes") if item.get("transit_minutes") is not None else 1e9,
        item.get("centre_km") if item.get("centre_km") is not None else 1e9,
    )


def write_results(listings: list[dict], out_prefix: str) -> tuple[str, str]:
    """Write ``<prefix>.csv`` and ``<prefix>.json``; return the two paths."""
    ordered = sorted(listings, key=_sort_key)

    csv_path = f"{out_prefix}.csv"
    json_path = f"{out_prefix}.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in ordered:
            writer.writerow(item)

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(ordered, fh, ensure_ascii=False, indent=2)

    return csv_path, json_path


def print_summary(listings: list[dict], max_rows: int = 25) -> None:
    """Print a compact table of the top results to stdout."""
    ordered = sorted(listings, key=_sort_key)
    print(f"\n{len(ordered)} matching listing(s):\n")
    if not ordered:
        return

    header = f"{'price':>9}  {'m2':>4}  {'bed':>3}  {'km':>5}  {'min':>4}  location"
    print(header)
    print("-" * len(header))
    for item in ordered[:max_rows]:
        print(
            f"{_fmt(item.get('price')):>9}  "
            f"{_fmt(item.get('size_m2')):>4}  "
            f"{_fmt(item.get('rooms')):>3}  "
            f"{_fmt(item.get('centre_km')):>5}  "
            f"{_fmt(item.get('transit_minutes')):>4}  "
            f"{(item.get('location') or '')[:40]}"
        )
    if len(ordered) > max_rows:
        print(f"... and {len(ordered) - max_rows} more (see output files)")


def _fmt(value: Optional[object]) -> str:
    return "-" if value is None else str(value)
