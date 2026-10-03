import json
import os

from terrahour.places import City
from terrahour.state import config_path, load_config, state_from_config
from terrahour.themes import C, apply_theme


def test_config_path_honours_xdg(tmp_path):
    assert config_path() == os.path.join(str(tmp_path / "config"), "terrahour", "config.json")


def test_fresh_state_has_defaults():
    st = state_from_config()
    assert len(st.cities) == 9 and st.cities[0].name == "San Francisco"
    assert not st.h12 and st.work == (9, 17) and st.overlap and st.home is None
    assert st.weather == "off" and st.compact == "auto" and st.wheel == "zoom"
    assert C.name == "midnight"


def test_save_and_reload_round_trip():
    st = state_from_config()
    st.cities = [City("Rome", "Europe/Rome", 41.9, 12.5, 4), City("Lima", "America/Lima", -12.0, -77.0, 1)]
    st.h12, st.work, st.overlap, st.weather, st.compact, st.wheel = True, (8, 18), False, "c", "on", "scrub"
    st.night_shade = 0.5
    st.home = {"name": "Rome", "zone": "Europe/Rome"}
    st.alerts = [{"kind": "time", "name": "Rome", "zone": "Europe/Rome", "m": 540, "_last": "x"},
                 {"kind": "timer", "name": "timer", "at": 0}]
    apply_theme("nord")
    st.save()
    assert os.path.exists(config_path())

    apply_theme("midnight")
    st2 = state_from_config()
    assert [(c.name, c.zone, c.cidx) for c in st2.cities] == [("Rome", "Europe/Rome", 4), ("Lima", "America/Lima", 1)]
    assert st2.h12 and st2.work == (8, 18) and not st2.overlap
    assert st2.weather == "c" and st2.compact == "on" and st2.wheel == "scrub" and st2.night_shade == 0.5
    assert st2.home == {"name": "Rome", "zone": "Europe/Rome"}
    assert st2.alerts == [{"kind": "time", "name": "Rome", "zone": "Europe/Rome", "m": 540}]   # timers are not saved
    assert C.name == "nord"


def test_session_only_state_is_not_saved():
    st = state_from_config()
    st.persist = False
    st.h12 = True
    st.save()
    assert not os.path.exists(config_path())


def test_broken_config_falls_back_to_defaults():
    p = config_path()
    os.makedirs(os.path.dirname(p))
    with open(p, "w") as f:
        f.write("{not json")
    assert load_config() == {}
    st = state_from_config()
    assert len(st.cities) == 9


def test_bad_values_in_config_are_ignored():
    p = config_path()
    os.makedirs(os.path.dirname(p))
    with open(p, "w") as f:
        json.dump({"cities": [{"name": "X", "zone": "Not/AZone", "lat": 0, "lon": 0, "cidx": 0}],
                   "home": {"zone": "Not/AZone"}, "compact": "sometimes", "weather": "k", "work": [9],
                   "alerts": [{"kind": "bogus"}, "junk"]}, f)
    st = state_from_config()
    assert len(st.cities) == 9 and st.home is None and st.compact == "auto"
    assert st.weather == "off" and st.work == (9, 17) and st.alerts == []


def test_old_config_with_colours_instead_of_colour_index():
    p = config_path()
    os.makedirs(os.path.dirname(p))
    old_palette = [list(c) for c in C.PALETTE]
    with open(p, "w") as f:
        json.dump({"cities": [{"name": "A", "zone": "UTC", "lat": 0, "lon": 0, "color": old_palette[5]},
                              {"name": "B", "zone": "UTC", "lat": 0, "lon": 0, "color": [1, 2, 3]}]}, f)
    st = state_from_config()
    assert [c.cidx for c in st.cities] == [5, 1]


def test_rows_and_cursor_switch_with_the_market_view(state):
    assert state.rows() is state.cities
    state.set_cursor(3)
    assert state.cursor() == 3
    state.markets = True
    assert state.rows()[0].sessions and state.cursor() == 0
    state.set_cursor(2)
    state.markets = False
    assert state.cursor() == 3


def test_say_sets_a_timed_message(state):
    state.say("hello")
    text, colour, until = state.msg
    assert text == "hello" and colour == C.TEXT and until > 0
