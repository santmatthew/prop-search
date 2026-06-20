"""Offline unit tests — no network or API keys required."""

from prop_search.conditions import excluded_condition, filter_out_conditions
from prop_search.config import SearchConfig
from prop_search.dedup import dedup
from prop_search.exclude import apply_exclusions, listing_id
from prop_search.floors import filter_out_basement, is_basement
from prop_search.geo import filter_by_centre, haversine_km
from prop_search.geocode import _too_coarse
from prop_search.idealista_url import build_search_url
from prop_search.models import Listing
from prop_search.parsing import parse_price, parse_rooms, parse_size
from prop_search.sources.fotocasa import _to_listing as fotocasa_to_listing
from prop_search.sources.idealista import _to_listing as idealista_to_listing
from prop_search.sources.redpiso import _to_listing as redpiso_to_listing
from prop_search.transit import _parse_duration, filter_by_transit
from prop_search.output import write_results


def L(**kw) -> Listing:
    kw.setdefault("source", "idealista")
    return Listing(**kw)


def test_build_search_url_default_filters():
    url = build_search_url(SearchConfig())
    assert url == (
        "https://www.idealista.com/venta-viviendas/madrid-madrid/"
        "con-precio-hasta_380000,precio-desde_250000,"
        "metros-cuadrados-mas-de_70,de-dos-dormitorios/"
    )


def test_build_search_url_high_bedrooms_falls_back():
    assert "de-cuatro-cinco-habitaciones-o-mas" in build_search_url(SearchConfig(min_bedrooms=9))


def test_parse_helpers():
    assert parse_price("€485,000") == 485000
    assert parse_price("360.000 €") == 360000
    assert parse_price(299000) == 299000
    assert parse_price(None) is None
    assert parse_size("90 m² · 3 hab.") == 90
    assert parse_rooms("90 m² · 3 hab.") == 3


def test_idealista_to_listing():
    out = idealista_to_listing({
        "propertyCode": "123",
        "price": "€350,000",
        "size": 85,
        "rooms": 2,
        "neighborhood": "Salamanca", "municipality": "Madrid",
        "url": "https://www.idealista.com/inmueble/123/",
        "latitude": 40.42, "longitude": -3.69,
    })
    assert out.source == "idealista" and out.id == "123"
    assert out.price == 350000 and out.size_m2 == 85 and out.rooms == 2
    assert out.lat == 40.42 and out.lng == -3.69


def test_fotocasa_to_listing():
    out = fotocasa_to_listing({
        "id": 189660685,
        "transactions": [{"transactionTypeId": 1, "value": [320000]}],
        "features": [{"key": "surface", "value": [80]},
                     {"key": "rooms", "value": [2]},
                     {"key": "floor", "value": [3]}],
        "address": {"ubication": "Calle X, Carabanchel",
                    "coordinates": {"latitude": 40.41, "longitude": -3.70}},
        "detail": {"es": "/es/comprar/vivienda/madrid-capital/abc/189660685/d"},
        "description": "Piso luminoso",
    })
    assert out.source == "fotocasa" and out.price == 320000 and out.size_m2 == 80
    assert out.rooms == 2 and out.url.startswith("https://www.fotocasa.es/")
    assert out.lat == 40.41 and out.location == "Calle X, Carabanchel"


def test_redpiso_to_listing():
    out = redpiso_to_listing({
        "code": "RP1",
        "price": 275000,
        "cadastre_property_summary": {"meters": 97, "bedrooms": 2},
        "display_location": "Calle X, Madrid",
        "slug": "piso-en-venta-RP1",
        "short_description": "Bonito piso",
    })
    assert out.source == "redpiso" and out.price == 275000 and out.size_m2 == 97
    assert out.url == "https://www.redpiso.es/inmueble/piso-en-venta-RP1"
    assert out.lat is None  # geocoded later


def test_redpiso_builds_precise_address_from_structured_location():
    # display_location is vague ("Madrid") but structured fields pin the street.
    out = redpiso_to_listing({
        "code": "RP2",
        "price": 300000,
        "cadastre_property_summary": {"meters": 80, "bedrooms": 2},
        "display_location": "Madrid",
        "slug": "x",
        "location": {
            "street": {"road_type": {"name": "Calle"}, "name": "de Camarena"},
            "number": 282,
            "quarter": {"name": "Aluche"},
            "district": {"name": "Latina"},
            "place": {"name": "Madrid"},
        },
    })
    assert out.location == "Calle de Camarena, 282, Aluche, Latina, Madrid"


def test_excluded_condition_detection():
    assert excluded_condition("Venta de la NUDA PROPIEDAD de un ático") == "nuda_propiedad"
    assert excluded_condition("Piso alquilado, con inquilinos") == "tenants"
    assert excluded_condition("Vivienda ocupada ilegalmente") == "squatters"
    assert excluded_condition("Ocupación ilegal, precio rebajado") == "squatters"
    # Negations / good listings must NOT match
    assert excluded_condition("Vivienda en plena propiedad, libre") is None
    assert excluded_condition("Sin inquilinos, libre de okupas") is None
    assert excluded_condition("Luminoso piso exterior reformado") is None
    assert excluded_condition(None) is None


def test_filter_out_conditions_all_sources():
    listings = [
        L(source="idealista", id="ok", details="Piso reformado y luminoso"),
        L(source="fotocasa", id="nuda", details="VENTA DE LA NUDA PROPIEDAD"),
        L(source="redpiso", id="ten", details="Se vende alquilado con inquilinos"),
        L(source="fotocasa", id="okupa", details="Atención: ocupada ilegalmente"),
    ]
    kept, counts = filter_out_conditions(listings)
    assert [k.id for k in kept] == ["ok"]
    assert counts == {"nuda_propiedad": 1, "tenants": 1, "squatters": 1}


def test_geocoder_rejects_city_level_results():
    assert _too_coarse({"addresstype": "city"})
    assert _too_coarse({"addresstype": "administrative"})
    assert _too_coarse({"type": "municipality"})
    assert not _too_coarse({"addresstype": "road"})
    assert not _too_coarse({"addresstype": "house"})
    assert not _too_coarse({"addresstype": "suburb"})


def test_basement_detection_and_filter():
    assert is_basement("Sótano interior") and is_basement("semi-sotano")
    assert not is_basement("Bajo exterior con patio")
    kept = filter_out_basement([
        L(id="a", details="Planta 2ª"),
        L(id="b", details="Atico con sótano trastero"),  # 'sotano' -> drop
        L(id="c", floor="st"),                            # basement code -> drop
        L(id="d", floor="Bajo"),
    ])
    assert [k.id for k in kept] == ["a", "d"]


def test_listing_id_and_exclusions():
    assert listing_id(L(id="123")) == "123"
    assert listing_id(L(url="https://www.idealista.com/inmueble/110706020/")) == "110706020"
    kept = apply_exclusions(
        [L(id="110706020", location="Palacio, Centro"),
         L(id="x", location="Calle del Olivar, Lavapiés-Embajadores"),
         L(id="y", location="Arapiles, Chamberí")],
        exclude_ids=["110706020"], exclude_areas=["lavapies"])
    assert [k.id for k in kept] == ["y"]


def test_haversine_and_centre_filter():
    assert 1.0 < haversine_km(40.4168, -3.7038, 40.4076, -3.6908) < 2.0
    kept = filter_by_centre(
        [L(id="near", lat=40.4175, lng=-3.7045),
         L(id="far", lat=40.50, lng=-3.60),
         L(id="nocoords")],
        40.4168, -3.7038, 2.5)
    assert [k.id for k in kept] == ["near"] and kept[0].centre_km < 0.5


def test_dedup_merges_across_sources():
    listings = [
        L(source="idealista", id="i1", price=300000, size_m2=90, rooms=2,
          lat=40.4170, lng=-3.7040, url="https://idealista/1"),
        L(source="fotocasa", id="f1", price=305000, size_m2=91, rooms=2,
          lat=40.4171, lng=-3.7041, url="https://fotocasa/1"),  # same flat
        L(source="redpiso", id="r1", price=260000, size_m2=70, rooms=2,
          lat=40.4300, lng=-3.6800, url="https://redpiso/1"),   # different
    ]
    out = dedup(listings)
    assert len(out) == 2
    primary = out[0]
    assert primary.source == "idealista"
    assert "fotocasa" in primary.also_on
    assert "https://fotocasa/1" in primary.other_urls


def test_parse_duration():
    assert _parse_duration("1234s") == 1234.0
    assert _parse_duration(600) == 600.0
    assert _parse_duration(None) is None


class FakeTimer:
    def __init__(self, mapping):
        self.mapping = mapping

    def minutes(self, lat, lng, dest_lat, dest_lng):
        return self.mapping.get(lat)


def test_filter_by_transit():
    listings = [L(id="fast", lat=1.0, lng=0.0),
                L(id="slow", lat=2.0, lng=0.0),
                L(id="noroute", lat=3.0, lng=0.0)]
    kept = filter_by_transit(listings, FakeTimer({1.0: 20.0, 2.0: 55.0, 3.0: None}),
                             0.0, 0.0, 30)
    assert [k.id for k in kept] == ["fast"] and kept[0].transit_minutes == 20.0


def test_write_results(tmp_path):
    listings = [L(source="fotocasa", also_on=["idealista"], price=300000, size_m2=90,
                  rooms=3, location="Centro", centre_km=1.2, transit_minutes=18,
                  url="http://x", lat=40.4, lng=-3.7)]
    prefix = str(tmp_path / "out")
    csv_path, json_path, html_path = write_results(listings, prefix)
    assert open(csv_path).read().startswith("source,also_on,price")
    assert '"transit_minutes": 18' in open(json_path).read()
    page = open(html_path).read()
    assert "http://x" in page and "<table" in page
