import datetime as dt
import math

import pytest

from terrahour.astro import daylight, sun_pos, sun_times
from terrahour.places import City

UTC = dt.timezone.utc
LONDON = City("London", "Europe/London", 51.51, -0.13, 0)
TROMSO = City("Tromso", "Europe/Oslo", 69.65, 18.96, 0)


def test_declination_at_the_solstices_and_equinox():
    decl, _ = sun_pos(dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
    assert math.degrees(decl) == pytest.approx(23.4, abs=0.3)
    decl, _ = sun_pos(dt.datetime(2026, 12, 21, 12, tzinfo=UTC))
    assert math.degrees(decl) == pytest.approx(-23.4, abs=0.3)
    decl, _ = sun_pos(dt.datetime(2026, 3, 20, 12, tzinfo=UTC))
    assert abs(math.degrees(decl)) < 1.0


def test_daylight_is_full_at_noon_and_zero_at_midnight_on_the_equator():
    assert daylight(0, 0, 12, 0, 0) == 1.0
    assert daylight(0, 0, 0, 0, 0) == 0.0
    assert daylight(0, 180, 0, 0, 0) == 1.0          # the other side of the world
    assert 0.0 < daylight(0, 0, 6.0, 0, 0) < 1.0     # twilight band around sunrise


def test_sun_times_london_midsummer():
    rise, sett = sun_times(LONDON, dt.datetime(2026, 6, 21, 12, tzinfo=UTC))
    assert rise.tzinfo.key == "Europe/London"
    # published values for London on 21 June: sunrise 04:43, sunset 21:21 (BST)
    assert abs((rise - rise.replace(hour=4, minute=43)).total_seconds()) < 15 * 60
    assert abs((sett - sett.replace(hour=21, minute=21)).total_seconds()) < 15 * 60


def test_sun_times_polar():
    assert sun_times(TROMSO, dt.datetime(2026, 12, 21, 12, tzinfo=UTC)) == "polar night"
    assert sun_times(TROMSO, dt.datetime(2026, 6, 21, 12, tzinfo=UTC)) == "midnight sun"
