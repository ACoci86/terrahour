"""Drive the app through handle_key / handle_mouse exactly as the terminal loop would."""
import datetime as dt

from terrahour.ambient import amb_entries
from terrahour.compose import compose
from terrahour.keys import handle_key, handle_mouse
from terrahour.themes import C
from terrahour.worldmap import ZOOMS

RIGHT, LEFT, UP, DOWN = "\x1b[C", "\x1b[D", "\x1b[A", "\x1b[B"
SHIFT_RIGHT, SHIFT_UP = "\x1b[1;2C", "\x1b[1;2A"
PGUP, PGDN, ENTER, ESC = "\x1b[5~", "\x1b[6~", "\r", "\x1b"


def press(st, keys, live):
    """Feed keys one after another; returns True if the app asked to quit."""
    for k in keys:
        now = st.frozen or live
        if handle_key(st, k, live, now):
            return True
    return False


def type_text(st, text, live):
    press(st, list(text), live)


def test_quit(state, now):
    assert press(state, ["q"], now)
    assert press(state, ["\x03"], now)
    assert not press(state, ["x"], now)


def test_row_selection_wraps(state, now):
    press(state, ["j", "j"], now)
    assert state.sel == 2
    press(state, [UP] * 3, now)
    assert state.sel == 8
    press(state, [DOWN], now)
    assert state.sel == 0


def test_scrubbing_time(state, now):
    press(state, [RIGHT], now)
    assert state.frozen == now + dt.timedelta(minutes=15)
    press(state, [SHIFT_RIGHT], now)
    assert state.frozen == now + dt.timedelta(minutes=75)
    press(state, [PGDN], now)
    assert state.frozen == now + dt.timedelta(minutes=75, days=1)
    press(state, [PGUP, PGUP, LEFT], now)
    assert state.frozen == now + dt.timedelta(minutes=60, days=-1)
    press(state, ["r"], now)
    assert state.frozen is None


def test_goto_a_clock_time_in_the_selected_city(state, now):
    press(state, ["j", "j", "g"], now)                       # London is row 2
    assert state.mode == "goto"
    type_text(state, "15:30", now)
    press(state, [ENTER], now)
    assert state.mode is None
    assert state.frozen == dt.datetime(2026, 3, 18, 15, 30, tzinfo=dt.timezone.utc)


def test_goto_shows_an_error_and_stays_open(state, now):
    press(state, ["g"], now)
    type_text(state, "13pm", now)
    press(state, [ENTER], now)
    assert state.mode == "goto" and "am/pm" in state.err
    press(state, [ESC], now)
    assert state.mode is None and state.frozen is None


def test_add_a_city_offline(state, now):
    press(state, ["a"], now)
    assert state.mode == "add"
    type_text(state, "naples", now)
    assert state.results and state.results[0]["name"] == "Naples"
    press(state, [ENTER], now)
    assert state.mode is None
    assert state.cities[-1].name == "Naples" and state.cities[-1].zone == "Europe/Rome"
    assert state.sel == len(state.cities) - 1


def test_adding_a_duplicate_is_refused(state, now):
    n = len(state.cities)
    press(state, ["a"], now)
    type_text(state, "tokyo", now)
    press(state, [ENTER], now)
    assert len(state.cities) == n and "already" in state.msg[0]


def test_add_box_editing_keys(state, now):
    press(state, ["a"], now)
    type_text(state, "lond", now)
    press(state, ["\x7f"], now)                                 # backspace
    assert state.buf == "lon"
    press(state, [DOWN, DOWN, UP], now)
    assert state.ridx == 1
    press(state, ["\x15"], now)                                 # ctrl-u clears
    assert state.buf == "" and state.results == []
    press(state, [ESC], now)
    assert state.mode is None


def test_remove_city_and_keep_the_last_one(state, now):
    press(state, ["d"], now)
    assert state.cities[0].name == "New York" and len(state.cities) == 8
    state.cities = state.cities[:1]
    state.sel = 0
    press(state, ["x"], now)
    assert len(state.cities) == 1 and "last" in state.msg[0]


def test_move_city_up_and_down(state, now):
    press(state, ["J"], now)
    assert [c.name for c in state.cities[:2]] == ["New York", "San Francisco"] and state.sel == 1
    press(state, [SHIFT_UP], now)
    assert state.cities[0].name == "San Francisco" and state.sel == 0
    press(state, ["K"], now)                                    # already at the top: nothing happens
    assert state.sel == 0


def test_home_toggle_and_removing_home_clears_it(state, now):
    press(state, ["j", "j", "*"], now)
    assert state.home == {"name": "London", "zone": "Europe/London"}
    press(state, ["*"], now)
    assert state.home is None
    press(state, ["*", "d"], now)
    assert state.home is None and all(c.name != "London" for c in state.cities)


def test_toggles(state, now):
    press(state, ["t"], now)
    assert state.h12
    press(state, ["m"], now)
    assert not state.overlap
    press(state, ["w"], now)
    assert state.work == (8, 18)
    press(state, ["W"], now)
    assert state.weather == "c"
    press(state, ["c"], now)
    assert state.compact == "on"
    press(state, ["Z"], now)
    assert state.wheel == "scrub"
    press(state, [ENTER], now)
    assert state.focus


def test_theme_cycles_and_wraps(state, now):
    press(state, ["T"], now)
    assert C.name == "nord"
    press(state, ["T"] * 5, now)
    assert C.name == "midnight"


def test_market_view_blocks_city_editing(state, now):
    press(state, ["M"], now)
    assert state.markets
    for k in ("d", "a", "*", "D", "J"):
        press(state, [k], now)
        assert state.mode is None and "M" in state.msg[0]
    press(state, ["M"], now)
    assert not state.markets


def test_overlay_modes_open_and_close(state, now):
    press(state, ["?"], now)
    assert state.mode == "help"
    press(state, ["x"], now)
    assert state.mode is None
    press(state, ["D"], now)
    assert state.mode == "radar"
    press(state, [ESC], now)
    assert state.mode is None


def test_alerts_overlay_add_and_delete(state, now):
    press(state, ["A", "n"], now)
    assert state.mode == "alertnew"
    type_text(state, "in 25m", now)
    press(state, [ENTER], now)
    assert state.mode == "alerts" and len(state.alerts) == 1 and state.alerts[0]["kind"] == "timer"
    press(state, ["d"], now)
    assert state.alerts == []
    press(state, [ESC], now)
    assert state.mode is None


def test_zoom_keys(state, now):
    press(state, ["+", "+"], now)
    assert ZOOMS[state.mzi] == 3
    press(state, ["]"], now)
    assert state.tsi == 1
    press(state, ["0"], now)
    assert state.mzi == 0 and state.tsi == 0 and state.mcenter is None
    press(state, ["-"], now)
    assert "limit" in state.msg[0]


def test_ambient_mode_keys(state, now):
    press(state, ["V"], now)
    assert state.ambient and state.amb_pin is None
    press(state, [RIGHT], now)
    assert state.amb_pin == 1
    press(state, [LEFT, LEFT], now)
    assert state.amb_pin == len(amb_entries(state)) - 1       # wraps around the rotation list
    press(state, [" "], now)
    assert state.amb_pin is None
    press(state, ["m"], now)
    assert state.amb_drift
    press(state, ["V"], now)
    assert not state.ambient
    press(state, ["V"], now)
    assert press(state, ["q"], now)


class TestMouse:
    def meta(self, state, now):
        return compose(120, 40, state, now, now).meta

    def test_wheel_moves_the_selection_outside_the_map(self, state, now):
        meta = self.meta(state, now)
        handle_mouse(state, meta, 65, 0, 39, True, now, now)      # wheel down on the footer
        assert state.sel == 1
        handle_mouse(state, meta, 64, 0, 39, True, now, now)
        assert state.sel == 0

    def test_wheel_over_the_map_zooms(self, state, now):
        meta = self.meta(state, now)
        x0, y0, mw, mh = meta["map"][:4]
        handle_mouse(state, meta, 64, x0 + mw // 2, y0 + mh // 2, True, now, now)
        assert ZOOMS[state.mzi] == 2 and state.mcenter is not None

    def test_click_on_a_row_selects_it(self, state, now):
        meta = self.meta(state, now)
        y = next(y for y, i in meta["rows"].items() if i == 4)
        handle_mouse(state, meta, 0, 10, y, True, now, now)
        assert state.sel == 4

    def test_click_on_the_bars_jumps_in_time(self, state, now):
        meta = self.meta(state, now)
        xb, nb, ytop = meta["bars"][:3]
        handle_mouse(state, meta, 0, xb + nb // 2, ytop, True, now, now)
        assert state.frozen is not None and abs(state.frozen.hour - 12) <= 1 and state.frozen.date() == now.date()

    def test_click_on_live_chip_returns_to_live(self, state, now):
        state.frozen = now + dt.timedelta(hours=3)
        meta = self.meta(state, now)
        cx, cw = meta["chip"]
        handle_mouse(state, meta, 0, cx + 1, 0, True, now, now)
        assert state.frozen is None

    def test_click_on_a_map_marker_selects_that_city(self, state, now):
        meta = self.meta(state, now)
        i, mx, my, rect = meta["markers"][-1]
        handle_mouse(state, meta, 0, mx, my, True, now, now)
        assert state.sel == i

    def test_mouse_is_ignored_while_an_overlay_is_open(self, state, now):
        state.mode = "help"
        handle_mouse(state, self.meta(state, now), 65, 0, 39, True, now, now)
        assert state.sel == 0
