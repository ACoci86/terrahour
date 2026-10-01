"""Compose whole frames and check their shape and content (no terminal involved)."""
import datetime as dt
import re
import time

import pytest

from zone_timeline.canvas import Canvas, sgr
from zone_timeline.compose import compose, is_compact
from zone_timeline.themes import C, THEME_ORDER, apply_theme

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(cv):
    return [ANSI.sub("", ln) for ln in cv.lines()]


def test_canvas_put_clips_and_lines_have_exact_width():
    cv = Canvas(10, 3)
    cv.put(-2, 0, "hello", C.TEXT)
    cv.put(8, 1, "world", C.TEXT, None, True)
    cv.put(0, 5, "nope", C.TEXT)
    assert plain(cv) == ["llo       ", "        wo", "          "]
    assert all(ln.endswith("\x1b[0m") for ln in cv.lines())


def test_canvas_fill_sets_background():
    cv = Canvas(5, 1)
    cv.fill(1, 0, 2, C.AMBER)
    assert cv.st[0][1] == (None, C.AMBER, False) and cv.st[0][0] == (None, C.BG, False)


def test_sgr_sequences():
    assert sgr((None, None, False)) == "\x1b[0m"
    assert sgr(((1, 2, 3), (4, 5, 6), True)) == "\x1b[0;1;38;2;1;2;3;48;2;4;5;6m"


@pytest.mark.parametrize("size", [(120, 40), (100, 30), (80, 24), (200, 60)])
def test_full_frame_has_exact_dimensions(state, now, size):
    W, H = size
    cv = compose(W, H, state, now, now)
    lines = plain(cv)
    assert len(lines) == H and all(len(ln) == W for ln in lines)


def test_main_view_content(state, now):
    text = "\n".join(plain(compose(130, 40, state, now, now)))
    assert "zone-timeline" in text and "● LIVE" in text
    assert "14:30:00 UTC" in text and "Wed 18 Mar 2026" in text
    for name in ("San Francisco", "New York", "London", "Tokyo", "Sydney"):
        assert name in text
    assert "Overlap" in text and "UTC Offset" in text and "Status" in text
    assert "open · 2h30" in text            # London
    assert any(0x2800 <= ord(ch) <= 0x28FF for ch in text)     # the braille map


def test_columns_drop_out_as_the_terminal_gets_narrower(state, now):
    wide = "\n".join(plain(compose(130, 40, state, now, now)))
    mid = "\n".join(plain(compose(110, 40, state, now, now)))
    narrow = "\n".join(plain(compose(90, 40, state, now, now)))
    assert "Status" in wide and "Status" not in mid
    assert "UTC Offset" in mid and "UTC Offset" not in narrow
    assert "Time (Local)" in narrow


def test_frozen_time_shows_the_offset_chip(state, now):
    state.frozen = now + dt.timedelta(hours=2)
    text = "\n".join(plain(compose(120, 40, state, now + dt.timedelta(hours=2), now)))
    assert "⏸ +2h" in text and "LIVE" not in text


def test_home_city_is_marked(state, now):
    state.home = {"name": "London", "zone": "Europe/London"}
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "⌂" in text and "vs Home" in text and "home" in text


def test_markets_view(state, now):
    state.markets = True
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "Exchange" in text and "NYSE / Nasdaq" in text and "of 10 open now" in text


def test_twelve_hour_clock(state, now):
    state.h12 = True
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "2:30 PM" in text and "12h" in text


def test_compact_layout_is_chosen_for_small_panes(state):
    assert is_compact(state, 70, 14) and not is_compact(state, 120, 40)
    state.compact = "off"
    assert not is_compact(state, 70, 14)
    state.compact = "on"
    assert is_compact(state, 120, 40)


@pytest.mark.parametrize("size", [(70, 14), (40, 8), (30, 5), (20, 3)])
def test_compact_frames_have_exact_dimensions(state, now, size):
    W, H = size
    state.compact = "on"
    lines = plain(compose(W, H, state, now, now))
    assert len(lines) == H and all(len(ln) == W for ln in lines)
    assert "San F" in "\n".join(lines)                       # the name may be cut with an ellipsis


def test_compact_view_content(state, now):
    state.compact = "on"
    text = "\n".join(plain(compose(72, 16, state, now, now)))
    assert "● LIVE" in text and "14:30 UTC" in text and "Overlap" in text


def test_ambient_view(state, now):
    state.ambient, state.amb_t0 = True, time.time()
    lines = plain(compose(100, 30, state, now, now))
    assert len(lines) == 30 and all(len(ln) == 100 for ln in lines)
    text = "\n".join(lines)
    assert "█" in text and "V exit" in text and "San Francisco" in text


@pytest.mark.parametrize("mode,title", [("help", "Keys"), ("radar", "DST radar"), ("add", "Add city"),
                                        ("goto", "Go to time"), ("alerts", "Alerts"), ("alertnew", "New alert")])
def test_overlays_render(state, now, mode, title):
    state.mode = mode
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert title in text


def test_help_fits_in_a_narrow_terminal(state, now):
    state.mode = "help"
    lines = plain(compose(80, 45, state, now, now))
    assert "Keys" in "\n".join(lines) and all(len(ln) == 80 for ln in lines)


def test_add_overlay_lists_results(state, now):
    from zone_timeline.places import refresh_results
    state.mode, state.buf = "add", "naples"
    refresh_results(state)
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "Naples" in text and "Europe/Rome" in text and "UTC+1" in text


def test_alert_banner(state, now):
    state.banner = ("Timer finished", time.time() + 10)
    assert "♪  Timer finished" in "\n".join(plain(compose(120, 40, state, now, now)))


@pytest.mark.parametrize("theme", THEME_ORDER)
def test_every_theme_renders(state, now, theme):
    apply_theme(theme)
    cv = compose(120, 40, state, now, now)
    assert len(cv.lines()) == 40
    assert cv.st[5][5][1] == C.BG and C.name == theme


def test_narrow_terminal_shows_a_hint_instead_of_crashing(state, now):
    state.compact = "off"
    text = "\n".join(plain(compose(50, 30, state, now, now)))
    assert "too narrow" in text


def test_offline_mode_does_not_pretend_to_search_online(state, now):
    from zone_timeline.places import refresh_results
    state.mode, state.buf = "add", "xqzjvwk"
    refresh_results(state)
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "No match." in text and "online" not in text
