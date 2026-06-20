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


def write_results(listings: list, out_prefix: str, controls: Optional[dict] = None) -> tuple[str, str, str]:
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
        fh.write(render_html(ordered, controls=controls))

    return csv_path, json_path, html_path


def _default_controls(listings: list) -> dict:
    prices = [l.price for l in listings if l.price]
    mins = [l.transit_minutes for l in listings if l.transit_minutes is not None]
    kms = [l.centre_km for l in listings if l.centre_km is not None]
    return {
        "price_min": min(prices) if prices else 0,
        "price_max": max(prices) if prices else 500000,
        "price_default": max(prices) if prices else 500000,
        "transit_max": max(mins) if mins else 60,
        "transit_default": max(mins) if mins else 60,
        "centre_max": max(kms) if kms else 10,
        "has_transit": bool(mins),
    }


def render_html(listings: list, title: str = "Madrid property search",
                controls: Optional[dict] = None) -> str:
    """Return a self-contained, interactive HTML page (sliders + live filter)."""
    ordered = sorted(listings, key=_sort_key)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = {**_default_controls(ordered), **(controls or {})}

    data = [
        {
            "price": l.price,
            "size": l.size_m2,
            "rooms": l.rooms,
            "min": l.transit_minutes,
            "km": l.centre_km,
            "source": l.source,
            "sources": l.all_sources(),
            "also_on": l.also_on,
            "location": l.location or "",
            "url": l.url or "",
        }
        for l in ordered
    ]
    data_json = json.dumps(data, ensure_ascii=False)

    # Slider bounds (round price bounds to a clean step).
    price_min = int(c["price_min"] // 10000 * 10000)
    price_max = int(-(-c["price_max"] // 10000) * 10000)  # round up
    price_def = int(min(max(c["price_default"], price_min), price_max))
    tmax = int(-(-c["transit_max"] // 1))
    tdef = int(min(c["transit_default"], tmax))
    kmax = float(c["centre_max"])
    has_transit = c["has_transit"]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ --line:#e5e5e5; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 0; color: #1a1a1a; }}
  header {{ position: sticky; top: 0; background:#fff; padding: 14px 16px 10px;
           border-bottom: 1px solid var(--line); z-index: 5; }}
  h1 {{ font-size: 1.15rem; margin: 0 0 2px; }}
  .meta {{ color:#666; font-size:.8rem; margin-bottom:10px; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:14px 22px; align-items:flex-end; }}
  .ctl {{ display:flex; flex-direction:column; font-size:.78rem; color:#444; min-width:170px; }}
  .ctl label b {{ color:#0a64c2; }}
  input[type=range] {{ width: 200px; }}
  .srcs {{ display:flex; gap:12px; font-size:.82rem; align-items:center; }}
  .srcs label {{ display:flex; gap:4px; align-items:center; }}
  main {{ padding: 8px 16px 28px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .92rem; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
  th {{ background:#f5f5f7; }}
  td.num, th.num {{ text-align: right; white-space: nowrap; }}
  td.price {{ font-weight: 600; white-space: nowrap; }}
  a {{ color:#0a64c2; text-decoration:none; white-space:nowrap; }}
  tr.data td {{ border-bottom:none; }}
  tr.loc td {{ color:#777; font-size:.72rem; padding-top:0; padding-bottom:12px; }}
  .tag {{ color:#888; font-size:.78rem; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="meta">generated {generated} &middot; <span id="count"></span> &middot; drag sliders to widen/narrow</div>
  <div class="controls">
    <div class="ctl">
      <label>Max price &le; <b id="priceVal"></b></label>
      <input type="range" id="price" min="{price_min}" max="{price_max}" step="5000" value="{price_def}">
    </div>
    {'''<div class="ctl">
      <label>Max commute &le; <b id="minVal"></b> min</label>
      <input type="range" id="mins" min="0" max="''' + str(tmax) + '''" step="1" value="''' + str(tdef) + '''">
    </div>''' if has_transit else ''}
    <div class="ctl">
      <label>Max km from centre &le; <b id="kmVal"></b></label>
      <input type="range" id="km" min="0" max="{kmax:.1f}" step="0.5" value="{kmax:.1f}">
    </div>
    <div class="ctl">
      <span>Sources</span>
      <div class="srcs">
        <label><input type="checkbox" class="src" value="idealista" checked> idealista</label>
        <label><input type="checkbox" class="src" value="fotocasa" checked> fotocasa</label>
        <label><input type="checkbox" class="src" value="redpiso" checked> redpiso</label>
      </div>
    </div>
  </div>
</header>
<main>
  <table>
    <thead><tr>
      <th class="num">#</th><th>Price</th><th class="num">m²</th><th class="num">bed</th>
      {'<th class="num">min</th>' if has_transit else ''}<th class="num">km</th><th>Source</th><th>Link</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<script>
const DATA = {data_json};
const HAS_TRANSIT = {str(has_transit).lower()};
const $ = id => document.getElementById(id);
const priceEl=$('price'), minsEl=$('mins'), kmEl=$('km');
const fmtP = n => n==null ? '-' : '\\u20ac' + n.toLocaleString('en-US');

function activeSources() {{
  return new Set([...document.querySelectorAll('.src:checked')].map(c => c.value));
}}
function render() {{
  const maxP=+priceEl.value, maxK=+kmEl.value;
  const maxM = (HAS_TRANSIT && minsEl) ? +minsEl.value : Infinity;
  const srcs = activeSources();
  $('priceVal').textContent = fmtP(maxP);
  if (HAS_TRANSIT && minsEl) $('minVal').textContent = maxM;
  $('kmVal').textContent = maxK.toFixed(1);
  const rows = DATA.filter(d =>
      (d.price==null || d.price<=maxP) &&
      (d.km==null || d.km<=maxK) &&
      (d.min==null || d.min<=maxM) &&
      (d.sources||[d.source]).some(s => srcs.has(s)));
  const tb = $('rows'); tb.innerHTML='';
  rows.forEach((d,i) => {{
    const tr=document.createElement('tr'); tr.className='data';
    let src=d.source + (d.also_on&&d.also_on.length ? ` <span class="tag">+${{d.also_on.join(', ')}}</span>`:'');
    tr.innerHTML = `<td class="num">${{i+1}}</td>`
      + `<td class="price">${{fmtP(d.price)}}</td>`
      + `<td class="num">${{d.size??'-'}}</td>`
      + `<td class="num">${{d.rooms??'-'}}</td>`
      + (HAS_TRANSIT ? `<td class="num">${{d.min??'-'}}</td>`:'')
      + `<td class="num">${{d.km??'-'}}</td>`
      + `<td>${{src}}</td>`
      + `<td>${{d.url ? `<a href="${{d.url}}" target="_blank" rel="noopener">View \\u2197</a>`:'-'}}</td>`;
    const loc=document.createElement('tr'); loc.className='loc';
    const td=document.createElement('td'); td.colSpan = HAS_TRANSIT?8:7;
    td.textContent = d.location || '\\u2014'; loc.appendChild(td);
    tb.appendChild(tr); tb.appendChild(loc);
  }});
  $('count').textContent = rows.length + ' of ' + DATA.length + ' listings';
}}
[priceEl, minsEl, kmEl].forEach(el => el && el.addEventListener('input', render));
document.querySelectorAll('.src').forEach(c => c.addEventListener('change', render));
render();
</script>
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
