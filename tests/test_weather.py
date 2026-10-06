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
