"""Offline unit tests — no network or API keys required."""

from prop_search.config import SearchConfig
from prop_search.geo import filter_by_centre, haversine_km
from prop_search.idealista_url import build_search_url
from prop_search.scraper import normalize_listing, parse_price, parse_rooms, parse_size
from prop_search.transit import _parse_duration, filter_by_transit
from prop_search.output import write_results


def test_build_search_url_default_filters():
    url = build_search_url(SearchConfig())
    assert url == (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/"
        "con-precio-hasta_360000,metros-cuadrados-mas-de_80,de-dos-dormitorios/"
    )


def test_build_search_url_high_bedrooms_falls_back():
    url = build_search_url(SearchConfig(min_bedrooms=9))
    assert "de-cuatro-cinco-habitaciones-o-mas" in url


def test_parse_price_variants():
    assert parse_price("€485,000") == 485000
    assert parse_price("360.000 €") == 360000
    assert parse_price(299000) == 299000
    assert parse_price(None) is None


def test_parse_size_and_rooms_from_details():
    details = "90 m² · 3 hab. · 2º exterior"
    assert parse_size(details) == 90
    assert parse_rooms(details) == 3
    assert parse_size("no size here") is None


def test_normalize_listing_maps_fields():
    raw = {
        "title": "Flat in calle de Serrano",
        "price": "€350,000",
        "details": "85 m² · 2 hab.",
        "location": "Salamanca, Madrid",
        "url": "https://www.idealista.com/inmueble/123/",
        "latitude": 40.42,
        "longitude": -3.69,
    }
    out = normalize_listing(raw)
    assert out["price"] == 350000
    assert out["size_m2"] == 85
    assert out["rooms"] == 2
    assert out["lat"] == 40.42 and out["lng"] == -3.69


def test_haversine_known_distance():
    # Puerta del Sol -> Atocha station ~ 1.4 km
    d = haversine_km(40.4168, -3.7038, 40.4076, -3.6908)
    assert 1.0 < d < 2.0


def test_filter_by_centre_drops_far_and_missing():
    listings = [
        {"title": "near", "lat": 40.4175, "lng": -3.7045},   # ~0.1 km
        {"title": "far", "lat": 40.50, "lng": -3.60},        # ~12 km
        {"title": "nocoords"},
    ]
    kept = filter_by_centre(listings, 40.4168, -3.7038, 2.5)
    assert [k["title"] for k in kept] == ["near"]
    assert kept[0]["centre_km"] < 0.5


def test_parse_duration():
    assert _parse_duration("1234s") == 1234.0
    assert _parse_duration(600) == 600.0
    assert _parse_duration(None) is None


class FakeTimer:
    """Stand-in for TransitTimer returning canned minutes by latitude."""

    def __init__(self, mapping):
        self.mapping = mapping

    def minutes(self, lat, lng, dest_lat, dest_lng):
        return self.mapping.get(lat)


def test_filter_by_transit():
    listings = [
        {"title": "fast", "lat": 1.0, "lng": 0.0},
        {"title": "slow", "lat": 2.0, "lng": 0.0},
        {"title": "noroute", "lat": 3.0, "lng": 0.0},
    ]
    timer = FakeTimer({1.0: 20.0, 2.0: 55.0, 3.0: None})
    kept = filter_by_transit(listings, timer, 0.0, 0.0, 30)
    assert [k["title"] for k in kept] == ["fast"]
    assert kept[0]["transit_minutes"] == 20.0


def test_write_results(tmp_path):
    listings = [
        {"title": "a", "price": 300000, "size_m2": 90, "rooms": 3,
         "location": "Centro", "centre_km": 1.2, "transit_minutes": 18,
         "url": "http://x", "lat": 40.4, "lng": -3.7},
    ]
    prefix = str(tmp_path / "out")
    csv_path, json_path = write_results(listings, prefix)
    assert open(csv_path).read().startswith("title,price,size_m2")
    assert '"transit_minutes": 18' in open(json_path).read()
