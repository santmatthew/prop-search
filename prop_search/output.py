"""Write results to CSV, JSON and HTML, and print a summary table."""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from typing import Optional

FIELDS = [
    "source",
    "also_on",
    "price",
    "size_m2",
    "rooms",
    "floor",
    "location",
    "centre_km",
    "transit_minutes",
    "url",
    "other_urls",
]


def _sort_key(item):
    # Sort by transit time when available, else by distance from centre.
    return (
        item.transit_minutes if item.transit_minutes is not None else 1e9,
        item.centre_km if item.centre_km is not None else 1e9,
    )


def write_results(listings: list, out_prefix: str) -> tuple[str, str, str]:
    """Write ``<prefix>.csv``, ``.json`` and ``.html``; return the three paths."""
    ordered = sorted(listings, key=_sort_key)
    rows = [l.to_row() for l in ordered]

    csv_path = f"{out_prefix}.csv"
    json_path = f"{out_prefix}.json"
    html_path = f"{out_prefix}.html"

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(ordered))

    return csv_path, json_path, html_path


def render_html(listings: list, title: str = "Madrid property search") -> str:
    """Return a self-contained HTML page with clickable listing links."""
    ordered = sorted(listings, key=_sort_key)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = []
    for i, item in enumerate(ordered, 1):
        url = item.url or ""
        loc = html.escape(str(item.location or ""))
        src = html.escape(item.source)
        if item.also_on:
            src += " <span class='also'>+ " + html.escape(", ".join(item.also_on)) + "</span>"
        price = item.price
        price_str = f"€{price:,}" if isinstance(price, int) else _fmt(price)
        link = (
            f'<a href="{html.escape(url)}" target="_blank" rel="noopener">View ↗</a>'
            if url else "&mdash;"
        )
        rows.append(
            "<tr class='data'>"
            f"<td class='num'>{i}</td>"
            f"<td class='price'>{price_str}</td>"
            f"<td class='num'>{_fmt(item.size_m2)}</td>"
            f"<td class='num'>{_fmt(item.rooms)}</td>"
            f"<td class='num'>{_fmt(item.transit_minutes)}</td>"
            f"<td class='num'>{_fmt(item.centre_km)}</td>"
            f"<td>{src}</td>"
            f"<td>{link}</td>"
            "</tr>"
            "<tr class='loc'>"
            f"<td colspan='8'>{loc or '&mdash;'}</td>"
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
  tr.data td {{ border-bottom: none; }}
  tr.loc td {{ color: #777; font-size: .72rem; padding-top: 0; padding-bottom: 12px; }}
  .also {{ color: #888; font-size: .8rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="meta">{len(ordered)} listing(s) &middot; generated {generated} &middot; sorted by transit time</div>
<table>
<thead><tr>
  <th class="num">#</th><th>Price</th><th class="num">m²</th><th class="num">bed</th>
  <th class="num">min</th><th class="num">km</th><th>Source</th><th>Link</th>
</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</body>
</html>
"""


def print_summary(listings: list, max_rows: int = 30) -> None:
    """Print a compact table of the top results to stdout."""
    ordered = sorted(listings, key=_sort_key)
    print(f"\n{len(ordered)} matching listing(s):\n")
    if not ordered:
        return

    header = f"{'price':>9}  {'m2':>4}  {'bed':>3}  {'km':>5}  {'min':>4}  {'source':<10}  location"
    print(header)
    print("-" * len(header))
    for item in ordered[:max_rows]:
        src = item.source + ("+" if item.also_on else "")
        print(
            f"{_fmt(item.price):>9}  "
            f"{_fmt(item.size_m2):>4}  "
            f"{_fmt(item.rooms):>3}  "
            f"{_fmt(item.centre_km):>5}  "
            f"{_fmt(item.transit_minutes):>4}  "
            f"{src:<10}  "
            f"{(item.location or '')[:38]}"
        )
    if len(ordered) > max_rows:
        print(f"... and {len(ordered) - max_rows} more (see output files)")


def _fmt(value: Optional[object]) -> str:
    return "-" if value is None else str(value)
