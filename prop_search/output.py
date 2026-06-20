"""Write results to CSV, JSON and HTML, and print a summary table."""

from __future__ import annotations

import csv
import html
import json
import urllib.parse
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
    "lat",
    "lng",
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
        "destination": "",
    }


def _eur(n) -> str:
    return "€{:,}".format(n) if isinstance(n, int) else "-"


def _maps_url(lat, lng, dest: str) -> str:
    return ("https://www.google.com/maps/dir/?api=1&origin="
            f"{lat},{lng}&destination={urllib.parse.quote(dest)}&travelmode=transit")


def _row_html(i: int, l, has_transit: bool, dest: str, ncols: int) -> str:
    """Static (no-JS-visible) two-row block for one listing, with filter data-*."""
    # Commute cell links to the Google Maps transit route when we have coords.
    if has_transit:
        if l.transit_minutes is not None and l.lat is not None and l.lng is not None and dest:
            href = html.escape(_maps_url(l.lat, l.lng, dest))
            min_cell = (f'<td class="num"><a href="{href}" target="_blank" rel="noopener" '
                        f'title="Transit route on Google Maps">{_fmt(l.transit_minutes)} ↗</a></td>')
        else:
            min_cell = f'<td class="num">{_fmt(l.transit_minutes)}</td>'
    else:
        min_cell = ""

    src = html.escape(l.source)
    if l.also_on:
        src += f' <span class="tag">+{html.escape(", ".join(l.also_on))}</span>'
    link = (f'<a href="{html.escape(l.url)}" target="_blank" rel="noopener">View ↗</a>'
            if l.url else "—")

    dprice = l.price if l.price is not None else ""
    dmin = l.transit_minutes if l.transit_minutes is not None else ""
    dkm = l.centre_km if l.centre_km is not None else ""
    dsrc = html.escape(" ".join(l.all_sources()))

    return (
        f'<tr class="data" data-price="{dprice}" data-min="{dmin}" data-km="{dkm}" data-src="{dsrc}">'
        f'<td class="num idx">{i}</td>'
        f'<td class="price">{_eur(l.price)}</td>'
        f'<td class="num">{_fmt(l.size_m2)}</td>'
        f'<td class="num">{_fmt(l.rooms)}</td>'
        f'{min_cell}'
        f'<td class="num">{_fmt(l.centre_km)}</td>'
        f'<td>{src}</td>'
        f'<td>{link}</td>'
        f'</tr>'
        f'<tr class="loc"><td colspan="{ncols}">{html.escape(l.location or "—")}</td></tr>'
    )


def render_html(listings: list, title: str = "Madrid property search",
                controls: Optional[dict] = None) -> str:
    """Self-contained HTML report.

    Rows are rendered as static HTML so they are visible even where JavaScript
    does not run (email/file previews). When JS is available, the sliders and
    source checkboxes simply show/hide rows (progressive enhancement).
    """
    ordered = sorted(listings, key=_sort_key)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    c = {**_default_controls(ordered), **(controls or {})}
    dest = c.get("destination") or ""
    has_transit = c["has_transit"]
    ncols = 8 if has_transit else 7

    price_min = int(c["price_min"] // 10000 * 10000)
    price_max = int(-(-c["price_max"] // 10000) * 10000)  # round up
    price_def = int(min(max(c["price_default"], price_min), price_max))
    tmax = int(-(-c["transit_max"] // 1)) or 1
    tdef = int(min(c["transit_default"], tmax))
    kmax = float(c["centre_max"])

    rows_html = "\n".join(_row_html(i, l, has_transit, dest, ncols)
                          for i, l in enumerate(ordered, 1))

    mins_ctl = (f'''<div class="ctl">
      <label>Max commute &le; <b id="minVal">{tdef}</b> min <span class="lim">(0&ndash;{tmax})</span></label>
      <input type="range" id="mins" min="0" max="{tmax}" step="1" value="{tdef}">
    </div>''' if has_transit else '')

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
  .ctl {{ display:flex; flex-direction:column; font-size:.78rem; color:#444; min-width:190px; }}
  .ctl label b {{ color:#0a64c2; }}
  .lim {{ color:#999; font-size:.72rem; }}
  input[type=range] {{ width: 210px; }}
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
  <div class="meta">generated {generated} &middot; <span id="count">{len(ordered)} listings</span> &middot; drag sliders to filter</div>
  <div class="controls">
    <div class="ctl">
      <label>Max price &le; <b id="priceVal">{_eur(price_def)}</b> <span class="lim">({_eur(price_min)}&ndash;{_eur(price_max)})</span></label>
      <input type="range" id="price" min="{price_min}" max="{price_max}" step="5000" value="{price_def}">
    </div>
    {mins_ctl}
    <div class="ctl">
      <label>Max km from centre &le; <b id="kmVal">{kmax:.1f}</b> <span class="lim">(0&ndash;{kmax:.1f})</span></label>
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
    <tbody>
{rows_html}
    </tbody>
  </table>
</main>
<script>
const $ = id => document.getElementById(id);
const priceEl=$('price'), minsEl=$('mins'), kmEl=$('km');
const fmtP = n => '\\u20ac' + (+n).toLocaleString('en-US');
const allRows = [...document.querySelectorAll('tr.data')];
function activeSources() {{
  return new Set([...document.querySelectorAll('.src:checked')].map(c => c.value));
}}
function render() {{
  const maxP=+priceEl.value, maxK=+kmEl.value;
  const maxM = minsEl ? +minsEl.value : Infinity;
  const srcs = activeSources();
  $('priceVal').textContent = fmtP(maxP);
  if (minsEl) $('minVal').textContent = maxM;
  $('kmVal').textContent = maxK.toFixed(1);
  let n = 0;
  allRows.forEach(tr => {{
    const p=tr.dataset.price, m=tr.dataset.min, k=tr.dataset.km;
    const rs=(tr.dataset.src||'').split(' ').filter(Boolean);
    const show = (p===''||+p<=maxP) && (k===''||+k<=maxK) && (m===''||+m<=maxM)
                 && rs.some(s => srcs.has(s));
    tr.style.display = show ? '' : 'none';
    const loc = tr.nextElementSibling;
    if (loc && loc.classList.contains('loc')) loc.style.display = show ? '' : 'none';
    if (show) {{ n++; const idx=tr.querySelector('.idx'); if(idx) idx.textContent=n; }}
  }});
  $('count').textContent = n + ' of ' + allRows.length + ' shown';
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
