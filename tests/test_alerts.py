import datetime as dt
import time

from zone_timeline.alerts import alert_city, check_alerts, parse_alert, resolve_place
from zone_timeline.overlays import alert_desc


def test_resolve_place_prefers_your_cities_then_exchanges_then_the_database(state):
    assert resolve_place(state, "tokyo") == ("Tokyo", "Asia/Tokyo", False)
    assert resolve_place(state, "nyse") == ("NYSE / Nasdaq", "America/New_York", True)
    assert resolve_place(state, "naples") == ("Naples", "Europe/Rome", False)
    assert resolve_place(state, "") == ("San Francisco", "America/Los_Angeles", False)     # the selected row
    assert resolve_place(state, "xqzjvwk") is None


def test_parse_timer(state):
    a, err = parse_alert("in 25m", state)
    assert err == "" and a["kind"] == "timer" and abs(a["at"] - (time.time() + 1500)) < 2
    a, _ = parse_alert("in 1h 30", state)
    assert abs(a["at"] - (time.time() + 5400)) < 2
    assert parse_alert("in 0m", state)[1].startswith("Timer must")


def test_parse_daily_time(state):
    a, err = parse_alert("9am tokyo", state)
    assert err == "" and a == {"kind": "time", "name": "Tokyo", "zone": "Asia/Tokyo", "m": 540}
    a, _ = parse_alert("17:45", state)
    assert a["name"] == "San Francisco" and a["m"] == 17 * 60 + 45


def test_parse_open_close(state):
    a, err = parse_alert("open new york", state)
    assert err == "" and a == {"kind": "open", "name": "New York", "zone": "America/New_York", "market": False}
    a, _ = parse_alert("close NYSE", state)
    assert a["kind"] == "close" and a["market"]


def test_parse_errors(state):
    assert "find" in parse_alert("open xqzjvwk", state)[1]
    assert "am/pm" in parse_alert("14pm tokyo", state)[1]
    assert parse_alert("what", state)[1].startswith("Try:")


def test_alert_city_for_markets_and_cities():
    assert alert_city({"kind": "open", "name": "NYSE / Nasdaq", "market": True}).sessions
    c = alert_city({"kind": "open", "name": "Rome", "zone": "Europe/Rome"})
    assert c.zone == "Europe/Rome" and c.sessions is None


def test_alert_desc():
    assert alert_desc({"kind": "time", "name": "Tokyo", "m": 540}) == "09:00 daily · Tokyo"
    assert alert_desc({"kind": "open", "name": "NYSE"}) == "when NYSE opens"
    assert alert_desc({"kind": "timer", "at": time.time() + 125}).startswith("timer · fires in 2m")


def test_timer_fires_once_and_is_removed(state):
    state.alerts = [{"kind": "timer", "name": "timer", "at": time.time() - 1},
                    {"kind": "timer", "name": "timer", "at": time.time() + 999}]
    assert check_alerts(state, dt.datetime.now(dt.timezone.utc)) == ["Timer finished"]
    assert len(state.alerts) == 1


def test_daily_alert_fires_at_the_minute_in_that_zone(state):
    state.alerts = [{"kind": "time", "name": "Tokyo", "zone": "Asia/Tokyo", "m": 540}]
    live = dt.datetime(2026, 3, 18, 0, 0, tzinfo=dt.timezone.utc)      # 09:00 in Tokyo
    assert check_alerts(state, live) == ["09:00 in Tokyo"]
    assert check_alerts(state, live) == []                               # not twice on the same day
    assert check_alerts(state, live + dt.timedelta(days=1)) == ["09:00 in Tokyo"]


def test_open_alert_fires_on_the_transition(state):
    state.alerts = [{"kind": "open", "name": "London", "zone": "Europe/London", "market": False}]
    before = dt.datetime(2026, 3, 18, 8, 59, tzinfo=dt.timezone.utc)
    assert check_alerts(state, before) == []                             # first look just records the state
    assert check_alerts(state, before + dt.timedelta(minutes=1)) == ["London is open"]
    assert check_alerts(state, before + dt.timedelta(hours=9)) == []      # closing is not an "open" alert
