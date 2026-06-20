# prop-search

Find Madrid flats across **idealista**, **fotocasa** and **redpiso** that match
your criteria, deduplicate across portals, then narrow to homes within `n`
minutes of a chosen location **by public transport**.

## How it works

Each source is an adapter that translates its portal into one common `Listing`
structure (`prop_search/models.py`); the rest of the pipeline is source-agnostic:

1. **Fetch** from each source with your base filters (price, size, bedrooms):
   - **idealista** — via an [Apify](https://apify.com) actor that handles DataDome
     internally (returns coordinates).
   - **fotocasa** — via an Apify actor by search URL (returns coordinates).
   - **redpiso** — directly via its internal JSON API (`/api/properties`); no
     coordinates, so these are geocoded.
2. **Filter**: drop basements/semi-basements and manual exclusions (by id/area).
3. **Geocode** listings missing coordinates (free OpenStreetMap Nominatim) and keep
   those within `--max-centre-km` of Madrid's centre (Puerta del Sol).
4. **Dedup**: merge the same flat appearing on multiple portals (close price +
   size + location); the duplicates are recorded on the survivor (`also_on`).
5. **Transit filter**: call the **Google Routes API** (transit, arrive-by-9am
   weekday) and keep listings reachable within `--max-minutes` of your destination.
6. **Output** `results.csv` / `.json` / `.html`, sorted by travel time.

### Sources & cost

| Source | How | Cost |
|---|---|---|
| idealista | Apify actor | ~$0.0009/result (free Apify credit covers it) |
| fotocasa | Apify actor | ~$1/1k results; **full sweeps need a paid Apify plan** (free plan caps ~5/run) |
| redpiso | its own JSON API | free |

Pick sources with `--sources idealista,redpiso` (default: all three).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in the two keys below
```

You need two keys in `.env`:

- `APIFY_TOKEN` — from <https://console.apify.com/account/integrations> (free trial credit).
- `GOOGLE_MAPS_API_KEY` — a Google Cloud key with **Routes API** *and*
  **Geocoding API** enabled.

## Usage

Default filters: Madrid, ≤ €360,000, ≥ 80 m², ≥ 2 bedrooms, ≤ 2.5 km from centre.

```bash
# Full run: scrape + centre filter + transit filter
python -m prop_search.main \
    --destination "Calle de Alcalá 1, Madrid" \
    --max-minutes 30

# Cheap test run (skip transit, cap listings)
python -m prop_search.main --no-transit --limit 20

# See the idealista search URL without scraping
python -m prop_search.main --print-url
```

### Key options

| Option | Meaning | Default |
|---|---|---|
| `--max-price` | Max price (€) | 360000 |
| `--min-size` | Min size (m²) | 80 |
| `--min-bedrooms` | Min bedrooms | 2 |
| `--max-centre-km` | Max distance from centre | 2.5 |
| `--destination` | Address or `lat,lng` for transit | — |
| `--max-minutes` | Max transit time (min) | — |
| `--no-transit` | Skip the transit step | off |
| `--limit` | Cap listings processed (testing) | — |
| `--out` | Output file prefix | `results` |

## Run from your phone (GitHub Actions)

No computer needed — trigger a run from the GitHub mobile app or browser:

1. **One-time:** in the repo, go to **Settings → Secrets and variables → Actions**
   and add two repository secrets:
   - `APIFY_TOKEN`
   - `GOOGLE_MAPS_API_KEY`
2. Go to the **Actions** tab → **Property search** → **Run workflow**.
3. Enter the destination and max minutes (other filters are optional overrides),
   then **Run workflow**.
4. Open the finished run and download the **results** artifact
   (`results.csv` / `results.json`).

The workflow is defined in `.github/workflows/search.yml`.

## Cost & caching

- Apify: ~$1 per 1,000 listings (free $5 starter credit).
- Geocoding/Routes calls are cached on disk in `.cache/`, so re-runs are free.
- The Routes API is only called for listings that already passed the (free)
  centre-distance filter.

## Tests

```bash
python -m pytest      # offline, no keys required
```

## Notes

- idealista's filter-URL slugs occasionally change. If results look off, open
  idealista, apply the filters in the UI, and compare the URL to
  `prop_search/idealista_url.py`.
- To go fully free later: swap `scraper.py` for a Playwright-stealth + login
  scraper and `transit.py` for a self-hosted OpenTripPlanner — the module
  interfaces stay the same.
