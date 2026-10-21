"""Compose whole frames and check their shape and content (no terminal involved)."""
import datetime as dt
import re
import time

import pytest

from terrahour.canvas import Canvas, sgr
from terrahour.compose import compose, is_compact
from terrahour.themes import C, THEME_ORDER, apply_theme

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
    assert "terrahour" in text and "● LIVE" in text
    assert "14:30:00 UTC" in text and "Wed 18 Mar 2026" in text
    for name in ("San Francisco", "New York", "London", "Tokyo", "Sydney"):
        assert name in text
    assert "Overlap" in text and "UTC Offset" in text and "Status" in text
    assert "open · 2h30" in text            # London
    assert any(0x2800 <= ord(ch) <= 0x28FF for ch in text)     # the braille map


def test_map_labels_can_show_the_local_time(state, now):
    text = "\n".join(plain(compose(130, 40, state, now, now)))
    assert "GMT (UTC+0)" in text and "JST (UTC+9)" in text        # zone and offset under the city name
    state.labels = "time"
    text = "\n".join(plain(compose(130, 40, state, now, now)))
    assert "GMT (UTC+0)" not in text and "JST (UTC+9)" not in text
    assert "23:30" in text                                        # Tokyo's clock on the map
    state.h12 = True
    text = "\n".join(plain(compose(130, 40, state, now, now)))
    assert "11:30 PM" in text


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


def test_ambient_map_follows_a_time_of_day(state, now):
    from terrahour.ambient import follow_lon
    state.ambient, state.amb_t0, state.amb_follow = True, time.time(), 9.0
    cv = compose(100, 30, state, now, now)            # 14:30 UTC: it is 09:00 at 82.5 degrees west
    assert cv.meta["map"][4] == follow_lon(9.0, now) == -82.5
    assert "09:00 here" in "\n".join(plain(cv))
    later = now + dt.timedelta(hours=2)
    assert follow_lon(9.0, later) == -112.5           # thirty degrees further west two hours on


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


@pytest.mark.parametrize("mode", ["help", "radar", "add", "goto", "alerts", "alertnew"])
@pytest.mark.parametrize("size", [(80, 24), (76, 16), (120, 40), (60, 12), (40, 8)])
def test_every_popup_stays_inside_the_window(state, now, mode, size):
    state.mode = mode
    text = "\n".join(plain(compose(size[0], size[1], state, now, now)))
    assert text.count("╭") == text.count("╰")                    # every box that opens also closes


def test_help_turns_pages_when_the_window_is_short(state, now):
    from terrahour.overlays import HELP_L, HELP_R, help_pages
    state.mode = "help"
    pages, cols, rows = help_pages(80, 24)
    assert len(pages) == 2 and cols == 1
    assert help_pages(104, 40)[1] == 2 and help_pages(100, 40)[1] == 1 and sum(len(p) for p in pages) == len(HELP_L) + len(HELP_R)
    text = "\n".join(plain(compose(80, 24, state, now, now)))
    assert "Keys  1/2" in text and "next page" in text and "scrub time 15 min" in text
    assert len(help_pages(120, 40)[0]) == 1                      # a big window shows everything at once


@pytest.mark.parametrize("W", [88, 100, 104, 120, 160])
def test_help_text_never_crosses_the_right_border(state, now, W):
    from terrahour.overlays import HELP_L, HELP_R, help_pages
    state.mode = "help"
    seen = ""
    for page in range(len(help_pages(W, 40)[0])):
        state.help_page = page
        lines = plain(compose(W, 40, state, now, now))
        top = next(ln for ln in lines if "Keys" in ln)
        left, right = top.index("╭"), top.index("╮")
        for ln in lines:
            if ln[left] == "│":
                assert ln[right] == "│", ln                       # the right border is intact on every row
        seen += "\n".join(lines)
    for _, d in HELP_L + HELP_R:
        assert d in seen                                          # and nothing had to be cut to achieve that


def test_add_overlay_lists_results(state, now):
    from terrahour.places import refresh_results
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
    assert cv.st[38][100][1] == C.BG and C.name == theme       # a cell outside the map keeps the plain background


def test_map_is_shaded_on_the_night_side_when_asked(state, now):
    flat = compose(120, 40, state, now, now)
    x0, y0, mw, mh = flat.meta["map"][:4]
    assert len({flat.st[y0 + mh // 2][x][1] for x in range(x0, x0 + mw)}) == 1     # off by default: one background
    state.night_shade = 0.5
    cv = compose(120, 40, state, now, now)
    x0, y0, mw, mh = cv.meta["map"][:4]
    row = [cv.st[y0 + mh // 2][x][1] for x in range(x0, x0 + mw)]
    assert len(set(row)) > 1                                    # not one flat background
    lum = [0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in row]
    assert max(lum) - min(lum) > 4                              # day and night backgrounds differ visibly


def has_map(lines):
    return any(0x2800 < ord(ch) <= 0x28FF for ln in lines[1:] for ch in ln)   # row 0 is the top bar, whose logo is braille too


def test_standard_80x24_terminal_keeps_the_map(state, now):
    lines = plain(compose(80, 24, state, now, now))
    assert has_map(lines)
    assert "1-8 of 9" in "\n".join(lines)                  # the table scrolls to make room for it
    assert all(ln.strip() for ln in lines)                 # and nothing is left blank


def test_very_short_terminal_drops_the_map_without_leaving_a_gap(state, now):
    lines = plain(compose(80, 18, state, now, now))
    assert not has_map(lines) and "╭" in lines[1]


@pytest.mark.parametrize("W", [76, 80, 84, 88, 92, 120])
def test_top_bar_items_never_run_into_each_other(state, now, W):
    state.alerts = [{"kind": "timer"}]
    top = plain(compose(W, 30, state, now, now))[0]
    assert re.search(r"\s{2}Wed 18 Mar 2026 {3}14:30:00 UTC {3}● LIVE", top)
    assert "work 09–17" in top


def test_table_sits_right_under_the_map_in_a_tall_window(state, now):
    lines = plain(compose(76, 50, state, now, now))
    table_top = next(i for i, ln in enumerate(lines) if "╭" in ln)
    assert table_top > 8 and all(ln.strip() for ln in lines[1:table_top])


@pytest.mark.parametrize("size", [(80, 24), (82, 27), (100, 30), (160, 45)])
@pytest.mark.parametrize("markets", [False, True])
def test_map_labels_never_overlap(state, now, size, markets):
    state.markets = markets
    cv = compose(size[0], size[1], state, now, now)
    rects = [m[3] for m in cv.meta["markers"]]
    assert len(rects) == len(state.rows())
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if a[2] - a[0] > 1 and b[2] - b[0] > 1:        # two labels, not bare dots
                assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_details_line_is_cut_at_whole_items(state, now):
    for W in range(76, 131):
        line = plain(compose(W, 40, state, now, now))[38].rstrip()
        assert len(line) <= W - 2
        assert re.search(r"(open(s in| ·) \d+h\d\d|☾ \d\d:\d\d|day \d+h\d\dm|from here|\(\d+d\)|\d+ \w{3}|°[EW])$", line), line


def test_narrow_terminal_shows_a_hint_instead_of_crashing(state, now):
    state.compact = "off"
    text = "\n".join(plain(compose(50, 30, state, now, now)))
    assert "too narrow" in text


def test_offline_mode_does_not_pretend_to_search_online(state, now):
    from terrahour.places import refresh_results
    state.mode, state.buf = "add", "xqzjvwk"
    refresh_results(state)
    text = "\n".join(plain(compose(120, 40, state, now, now)))
    assert "No match." in text and "online" not in text
