# prop-search

Find Madrid flats on **idealista.com** that match your criteria, then narrow them
to homes within `n` minutes of a chosen location **by public transport**.

## How it works

idealista is protected by DataDome (aggressive anti-bot), so this tool does **not**
scrape the site directly. Instead it runs a pipeline:

1. **Build** an idealista search URL from your base filters (price, size, bedrooms).
2. **Scrape** matching listings through a third-party scraping API
   ([Apify](https://apify.com) idealista actor — handles DataDome + proxies).
3. **Geocode** each listing (Google Geocoding API) and keep those within
   `--max-centre-km` of Madrid's centre (Puerta del Sol).
4. **Transit filter:** for the survivors, call the **Google Routes API** (transit
   mode) and keep listings reachable within `--max-minutes` of your destination.
5. **Output** `results.csv` + `results.json`, sorted by travel time.

> The idealista login is **not** needed for this approach — the scraping service
> handles access. Credentials are kept in `.env` only as a placeholder for a
> possible future login-based path.

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
