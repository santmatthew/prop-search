"""Write results to CSV and JSON and print a summary table."""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from typing import Optional

FIELDS = [
    "title",
    "price",
    "size_m2",
    "rooms",
    "floor",
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


def write_results(listings: list[dict], out_prefix: str) -> tuple[str, str, str]:
    """Write ``<prefix>.csv``, ``.json`` and ``.html``; return the three paths."""
    ordered = sorted(listings, key=_sort_key)

    csv_path = f"{out_prefix}.csv"
    json_path = f"{out_prefix}.json"
    html_path = f"{out_prefix}.html"

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in ordered:
            writer.writerow(item)

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(ordered, fh, ensure_ascii=False, indent=2)

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(ordered))

    return csv_path, json_path, html_path


def render_html(listings: list[dict], title: str = "Madrid property search") -> str:
    """Return a self-contained HTML page with clickable listing links."""
    ordered = sorted(listings, key=_sort_key)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = []
    for i, item in enumerate(ordered, 1):
        url = item.get("url") or ""
        loc = html.escape(str(item.get("location") or ""))
        price = item.get("price")
        price_str = f"€{price:,}" if isinstance(price, int) else _fmt(price)
        link = (
            f'<a href="{html.escape(url)}" target="_blank" rel="noopener">View on idealista ↗</a>'
            if url else "&mdash;"
        )
        rows.append(
            "<tr>"
            f"<td class='num'>{i}</td>"
            f"<td class='price'>{price_str}</td>"
            f"<td class='num'>{_fmt(item.get('size_m2'))}</td>"
            f"<td class='num'>{_fmt(item.get('rooms'))}</td>"
            f"<td class='num'>{_fmt(item.get('transit_minutes'))}</td>"
            f"<td class='num'>{_fmt(item.get('centre_km'))}</td>"
            f"<td>{loc}</td>"
            f"<td>{link}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 16px; color: #1a1a1a; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 4px; }}
  .meta {{ color: #666; font-size: .85rem; margin-bottom: 14px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .92rem; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e5e5; text-align: left;
           vertical-align: top; }}
  th {{ background: #f5f5f7; position: sticky; top: 0; }}
  td.num, th.num {{ text-align: right; white-space: nowrap; }}
  td.price {{ font-weight: 600; white-space: nowrap; }}
  a {{ color: #0a64c2; text-decoration: none; white-space: nowrap; }}
  tr:hover td {{ background: #fafafe; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="meta">{len(ordered)} listing(s) &middot; generated {generated} &middot; sorted by transit time</div>
<table>
<thead><tr>
  <th class="num">#</th><th>Price</th><th class="num">m²</th><th class="num">bed</th>
  <th class="num">min</th><th class="num">km</th><th>Location</th><th>Link</th>
</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</body>
</html>
"""


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
