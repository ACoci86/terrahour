import json

from zone_timeline.output import fit_line, json_output, line_output, render_parts, short_label


def test_short_label():
    assert short_label("San Francisco") == "SF"
    assert short_label("Tokyo") == "TOK"
    assert short_label("NYSE / Nasdaq") == "NN"
    assert short_label("Rio de Janeiro Norte Sul") == "RDJN"


def test_line_output_plain(state, now):
    line = line_output(state, now, tmux=False, color=False)
    assert line.startswith("SF 07:30 · NY 10:30 · LON 14:30 · UTC 14:30")
    assert "SYD 01:30+1" in line                      # already tomorrow in Sydney
    assert "\x1b" not in line


def test_line_output_with_seconds_and_12h(state, now):
    state.h12 = True
    assert line_output(state, now, False, False, seconds=True).startswith("SF 7:30:00 AM")


def test_line_output_colour_and_tmux(state, now):
    assert line_output(state, now, False, True).startswith("\x1b[38;2;")
    tm = line_output(state, now, True, False)
    assert tm.startswith("#[fg=#") and "#[default]" in tm


def test_render_parts_joins_with_a_dot_and_extra():
    assert render_parts([("a", (0, 0, 0)), ("b", (0, 0, 0))], extra=" +3") == "a · b +3"


def test_fit_line_collapses_what_does_not_fit(state, now):
    full = fit_line(state, now, 200, False)
    assert full == line_output(state, now, False, False)
    short = fit_line(state, now, 40, False)
    assert len(short) < 40 and short.endswith("+6")
    tiny = fit_line(state, now, 6, False)
    assert tiny == "SF 07"


def test_json_output(state, now):
    data = json.loads(json_output(state, now))
    assert data["utc"] == "2026-03-18T14:30:00+00:00"
    assert [c["name"] for c in data["cities"]][:3] == ["San Francisco", "New York", "London"]
    london = data["cities"][2]
    assert london == {"name": "London", "zone": "Europe/London", "local_time": "2026-03-18T14:30+00:00",
                      "utc_offset_minutes": 0, "abbreviation": "GMT", "open": True, "minutes_to_change": 150,
                      "next_clock_change": "2026-03-29T01:00+00:00"}
    tokyo = next(c for c in data["cities"] if c["name"] == "Tokyo")
    assert tokyo["next_clock_change"] is None and tokyo["utc_offset_minutes"] == 540
