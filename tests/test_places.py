import pytest

from zone_timeline.places import (ABBR, DEFAULT_NAMES, City, _dms, cities_from_args, city_db, default_cities,
                                  make_city, markets, next_cidx, parse_sessions, search_db)
from zone_timeline.themes import C


def test_city_db_is_big_and_well_formed():
    db = city_db()
    assert len(db) > 5000
    for e in db[:200]:
        assert {"name", "zone", "lat", "lon", "hay", "alts", "pop", "country"} <= set(e)
        assert -90 <= e["lat"] <= 90 and -180 <= e["lon"] <= 180


def test_curated_entries_win_over_geonames():
    """There is a London in Ontario too; the first London must be the one in England."""
    london = next(e for e in city_db() if e["name"] == "London")
    assert london["zone"] == "Europe/London"


def test_search_by_city_name():
    res = search_db("naples")
    assert res and res[0]["name"] == "Naples" and res[0]["zone"] == "Europe/Rome"


def test_search_is_accent_insensitive():
    res = search_db("são paulo")
    assert res and res[0]["name"].lower().startswith("sao paulo")


def test_search_by_zone_name_puts_the_zone_first():
    res = search_db("Asia/Tokyo")
    assert res[0]["zone"] == "Asia/Tokyo"


def test_search_by_country():
    res = search_db("new zealand")
    assert res and all(e["zone"].startswith("Pacific/") for e in res[:3])


def test_search_ambiguous_name_returns_several():
    res = search_db("springfield")
    assert len(res) >= 2 and len({e["zone"] for e in res}) >= 2


def test_search_empty_and_nonsense():
    assert search_db("   ") == []
    assert search_db("xqzjvwk") == []


def test_search_limit():
    assert len(search_db("san", limit=3)) == 3


def test_default_cities_match_default_names():
    cities = default_cities()
    assert [c.name for c in cities] == DEFAULT_NAMES
    assert [c.cidx for c in cities] == list(range(len(cities)))


def test_markets_have_sessions_and_are_weekday_only():
    ms = markets()
    assert len(ms) == 10
    for m in ms:
        assert m.weekdays and m.sessions
        for a, b in m.sessions:
            assert 0 <= a < b <= 24 * 60
    assert ms is markets()      # cached


def test_parse_sessions():
    assert parse_sessions("09:30-16:00") == [(570, 960)]
    assert parse_sessions("09:30-11:30,13:00-15:00") == [(570, 690), (780, 900)]


def test_city_info_uses_tz_abbreviation_or_fallback(now):
    loc, off, abbr = City("Mumbai", "Asia/Kolkata", 19.1, 72.9, 0).info(now)
    assert abbr == "IST" and off.total_seconds() == 5.5 * 3600 and loc.hour == 20
    # Dubai has no letter abbreviation in tzdata ("+04"), so the table supplies one
    assert City("Dubai", "Asia/Dubai", 25.2, 55.3, 0).info(now)[2] == ABBR["Asia/Dubai"]
    assert City("UTC", "UTC", 12.0, 0.0, 0).info(now)[2] == "UTC"


def test_city_colour_cycles_through_palette():
    assert City("a", "UTC", 0, 0, 0).color == C.PALETTE[0]
    assert City("a", "UTC", 0, 0, len(C.PALETTE) + 2).color == C.PALETTE[2]


def test_city_to_json_round_trip():
    c = City("Rome", "Europe/Rome", 41.9, 12.5, 3)
    j = c.to_json()
    assert j == {"name": "Rome", "zone": "Europe/Rome", "lat": 41.9, "lon": 12.5, "cidx": 3}


def test_next_cidx_picks_first_unused_colour():
    cities = [City("a", "UTC", 0, 0, 0), City("b", "UTC", 0, 0, 2)]
    assert next_cidx(cities) == 1
    assert next_cidx([]) == 0


def test_make_city_looks_up_coordinates_for_a_bare_zone():
    c = make_city({"name": "Berlin", "zone": "Europe/Berlin", "lat": None, "lon": None}, [])
    assert abs(c.lat - 52.5) < 1 and abs(c.lon - 13.4) < 1


def test_make_city_guesses_a_position_for_an_unknown_zone():
    c = make_city({"name": "Somewhere", "zone": "Etc/GMT-3", "lat": None, "lon": None}, [])
    assert c.lat == 20.0 and c.lon == 45.0


def test_cities_from_args_zone_label_and_city_name():
    out = cities_from_args(["Europe/Berlin", "Home=America/Chicago", "Naples", "Nap=Naples"])
    assert [c.name for c in out] == ["Berlin", "Home", "Naples", "Nap"]
    assert [c.zone for c in out] == ["Europe/Berlin", "America/Chicago", "Europe/Rome", "Europe/Rome"]
    assert len({c.cidx for c in out}) == 4


def test_cities_from_args_unknown_place_exits():
    with pytest.raises(SystemExit):
        cities_from_args(["Nope/Zone"])


def test_dms_parses_zone_tab_coordinates():
    assert _dms("+4042", 2) == pytest.approx(40.7, abs=0.01)
    assert _dms("-07400", 3) == pytest.approx(-74.0, abs=0.01)
    assert _dms("+515030", 2) == pytest.approx(51.8417, abs=0.001)
