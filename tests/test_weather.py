"""Weather fetch tests (network stubbed; never touches the real API)."""
import io
import json
from unittest import mock

from terrahour import weather


def _payload(temp):
    return json.dumps({"current": {"temperature_2m": temp, "weather_code": 0}}).encode()


def _fetch(temp):
    with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(_payload(temp))):
        weather._fetch_weather_batch([(45.0, 14.0)])


def test_finite_temperature_is_stored():
    _fetch(21.5)
    assert weather.WEATHER[(45.0, 14.0)]["t"] == 21.5


def test_non_finite_temperature_is_dropped_without_raising():
    _fetch(21.5)
    _fetch(float("nan"))
    assert weather.WEATHER[(45.0, 14.0)]["t"] == 21.5
    assert weather.W_STATE["err"] is not None


def test_utc_and_etc_zones_are_not_places():
    from terrahour.places import City
    assert not City("UTC", "UTC", 12.0, 0.0, 0).is_place
    assert not City("GMT-5", "Etc/GMT+5", 20.0, -75.0, 0).is_place
    assert City("London", "Europe/London", 51.5, -0.1, 0).is_place


def test_no_weather_is_fetched_or_shown_for_utc(monkeypatch):
    from terrahour.places import City
    utc, rome = City("UTC", "UTC", 12.0, 0.0, 0), City("Rome", "Europe/Rome", 41.9, 12.5, 1)
    monkeypatch.setattr(weather, "offline", lambda: False)
    monkeypatch.setitem(weather.W_STATE, "busy", False)
    monkeypatch.setitem(weather.W_STATE, "next", 0.0)
    asked = []
    monkeypatch.setattr(weather.threading, "Thread",
                        lambda target, args, daemon: mock.Mock(start=lambda: asked.extend(args[0])))
    weather.weather_refresh([utc, rome])
    assert asked == [weather._wkey(rome)]            # Burkina Faso is never asked about
    weather.WEATHER[weather._wkey(utc)] = {"t": 38.0, "code": 0, "ts": 1e12}
    assert weather.weather_cell(utc, "c") == ("—", weather.C.DIM)
