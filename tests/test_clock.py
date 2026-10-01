import datetime as dt
import time
from zoneinfo import ZoneInfo

import pytest

from zone_timeline import clock
from zone_timeline.clock import (dst_gap_change, dur, fmt_clock, fmt_delta, fmt_local, fmt_off, fmt_rel, is_open,
                                 local_zone, next_transition, overlap_window, parse_at, parse_goto, ref_offset,
                                 status_info, status_text, time_window, work_alpha)
from zone_timeline.places import City
from zone_timeline.state import State
from zone_timeline.themes import C

UTC = dt.timezone.utc
LONDON = City("London", "Europe/London", 51.51, -0.13, 0)
NEW_YORK = City("New York", "America/New_York", 40.71, -74.01, 1)
TOKYO = City("Tokyo", "Asia/Tokyo", 35.68, 139.69, 2)
NYSE = City("NYSE", "America/New_York", 40.71, -74.01, 3, sessions=[(570, 960)], weekdays=True)


def test_parse_at_assumes_utc_without_an_offset(now):
    assert parse_at("2026-03-18T14:30:00") == now
    assert parse_at("2026-03-18T14:30:00Z") == now
    assert parse_at("2026-03-18 15:30+01:00") == now


def test_fmt_off():
    assert fmt_off(dt.timedelta(0)) == "UTC+0"
    assert fmt_off(dt.timedelta(hours=5, minutes=30)) == "UTC+5:30"
    assert fmt_off(dt.timedelta(hours=-7)) == "UTC-7"
    assert fmt_off(dt.timedelta(hours=-3, minutes=-30)) == "UTC-3:30"


def test_fmt_rel():
    assert fmt_rel(dt.timedelta(0)) == "same"
    assert fmt_rel(dt.timedelta(hours=9)) == "+9h"
    assert fmt_rel(dt.timedelta(hours=-5, minutes=-45)) == "-5:45h"


def test_fmt_clock_and_local(now):
    assert fmt_clock(now, False) == "14:30"
    assert fmt_clock(now, True) == "2:30 PM"
    assert fmt_local(now, False) == "Wed 14:30"
    assert fmt_clock(now.replace(hour=0), True) == "12:30 AM"


def test_fmt_delta():
    assert fmt_delta(0) == "+0m"
    assert fmt_delta(90 * 60) == "+1h30m"
    assert fmt_delta(-86400) == "-1d"
    assert fmt_delta(86400 + 3600 + 60) == "+1d1h1m"


def test_dur():
    assert dur(5) == "5m"
    assert dur(65) == "1h05"
    assert dur(1500) == "1d1h"


def test_work_alpha_shape():
    assert work_alpha(12, 9, 17) == 1.0
    assert work_alpha(3, 9, 17) == pytest.approx(0.12)
    assert work_alpha(17, 9, 17) == pytest.approx(0.55)     # fades out after work
    assert 0.12 < work_alpha(8, 9, 17) < 1.0                # fades in before work
    assert work_alpha(8.9, 9, 17) > work_alpha(7.1, 9, 17)


def test_is_open_city_ignores_weekends_but_exchange_does_not():
    saturday_noon = dt.datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("Europe/London"))
    assert is_open(LONDON, saturday_noon, (9, 17))
    saturday_ny = dt.datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert not is_open(NYSE, saturday_ny, (9, 17))


def test_is_open_exchange_sessions_are_half_open_intervals():
    ny = ZoneInfo("America/New_York")
    assert not is_open(NYSE, dt.datetime(2026, 3, 18, 9, 29, tzinfo=ny), (9, 17))
    assert is_open(NYSE, dt.datetime(2026, 3, 18, 9, 30, tzinfo=ny), (9, 17))
    assert not is_open(NYSE, dt.datetime(2026, 3, 18, 16, 0, tzinfo=ny), (9, 17))


def test_status_info_counts_minutes_to_the_next_change(now):
    assert status_info(LONDON, now, (9, 17)) == (True, 150)           # closes at 17:00
    assert status_info(TOKYO, now, (9, 17)) == (False, 9 * 60 + 30)   # 23:30 in Tokyo, opens 09:00
    o, mins = status_info(NYSE, now, (9, 17))
    assert o and mins == 330                                          # 10:30 EDT, closes 16:00


def test_status_text_colours(now):
    assert status_text(LONDON, now, (9, 17)) == ("open · 2h30", C.GREEN)
    assert status_text(LONDON, now.replace(hour=16, minute=30), (9, 17)) == ("open · 30m", C.AMBER)
    assert status_text(TOKYO, now, (9, 17))[0] == "opens in 9h30"


def test_next_transition_finds_the_uk_spring_change(now):
    inst, old, new = next_transition(ZoneInfo("Europe/London"), now)
    assert inst == dt.datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert old == dt.timedelta(0) and new == dt.timedelta(hours=1)


def test_next_transition_is_none_without_dst(now):
    assert next_transition(ZoneInfo("Asia/Tokyo"), now) is None
    assert next_transition(UTC, now) is None


def test_dst_gap_change_against_home(now):
    """Home in Tokyo (no DST): the gap to London changes when London springs forward."""
    st = State()
    st.home = {"name": "Tokyo", "zone": "Asia/Tokyo"}
    inst, g0, g1 = dst_gap_change(LONDON, st, now)
    assert inst == dt.datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert g0 == dt.timedelta(hours=-9) and g1 == dt.timedelta(hours=-8)


def test_dst_gap_change_is_none_when_both_shift_together(now):
    st = State()
    st.home = {"name": "Berlin", "zone": "Europe/Berlin"}
    assert dst_gap_change(LONDON, st, now) is None


def test_overlap_window_london_new_york(now):
    day0 = now.replace(hour=0, minute=0)
    # 18 March: the US is already on DST, the UK is not, so New York is UTC-4
    assert overlap_window([LONDON, NEW_YORK], day0, 9, 17) == (13 * 60, 17 * 60)


def test_overlap_window_none_and_full(now):
    day0 = now.replace(hour=0, minute=0)
    assert overlap_window([LONDON, TOKYO], day0, 9, 17) is None
    assert overlap_window([LONDON, LONDON], day0, 0, 24) == (0, 1440)


def test_time_window(now):
    st = State()
    assert time_window(st, now) == (now.replace(hour=0, minute=0), 24.0)
    st.tsi = 2                                                        # 6-hour window centred on now
    assert time_window(st, now) == (now - dt.timedelta(hours=3), 6.0)


def test_ref_offset_uses_home_when_set(now):
    st = State()
    assert ref_offset(st, now) == dt.timedelta(0)                     # system zone is UTC in tests
    st.home = {"name": "Tokyo", "zone": "Asia/Tokyo"}
    assert ref_offset(st, now) == dt.timedelta(hours=9)


def test_local_zone_reads_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Rome")
    time.tzset()
    monkeypatch.setattr(clock, "_local_zone", "unset")
    assert local_zone().key == "Europe/Rome"


class TestParseGoto:
    tz = ZoneInfo("Asia/Tokyo")

    def test_empty_means_live(self, now):
        assert parse_goto("", self.tz, now) == (None, "")
        assert parse_goto("now", self.tz, now) == (None, "")

    def test_relative(self, now):
        assert parse_goto("+2h", self.tz, now) == (now + dt.timedelta(hours=2), "")
        assert parse_goto("-45m", self.tz, now) == (now - dt.timedelta(minutes=45), "")
        assert parse_goto("+1d", self.tz, now) == (now + dt.timedelta(days=1), "")
        assert parse_goto("+1.5", self.tz, now) == (now + dt.timedelta(hours=1.5), "")

    def test_clock_time_in_the_given_zone(self, now):
        # it is 23:30 on the 18th in Tokyo, and a bare clock time stays on that local day
        t, err = parse_goto("15:30", self.tz, now)
        assert err == "" and t == dt.datetime(2026, 3, 18, 6, 30, tzinfo=UTC)   # 15:30 JST on the 18th
        assert parse_goto("3pm", self.tz, now)[0] == dt.datetime(2026, 3, 18, 6, 0, tzinfo=UTC)
        assert parse_goto("12am", self.tz, now)[0] == dt.datetime(2026, 3, 17, 15, 0, tzinfo=UTC)

    def test_z_suffix_means_utc(self, now):
        assert parse_goto("15:30z", self.tz, now)[0] == now.replace(hour=15, minute=30)
        assert parse_goto("9 utc", self.tz, now)[0] == now.replace(hour=9, minute=0)

    def test_full_date(self, now):
        assert parse_goto("2026-10-05 09:00", self.tz, now)[0] == dt.datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
        assert parse_goto("2026-10-05T09:00z", self.tz, now)[0] == dt.datetime(2026, 10, 5, 9, 0, tzinfo=UTC)

    def test_errors(self, now):
        assert parse_goto("13pm", self.tz, now) == (None, "Hour must be 1-12 with am/pm.")
        assert parse_goto("25:00", self.tz, now) == (None, "That isn't a valid time.")
        assert parse_goto("2026-02-30 10:00", self.tz, now) == (None, "That date doesn't exist.")
        assert parse_goto("nonsense", self.tz, now)[1].startswith("Try ")
