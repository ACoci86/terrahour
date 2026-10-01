"""Keyboard and mouse handling: every key press ends up in :func:`handle_key`."""
import datetime as dt
import re
import time
from zoneinfo import ZoneInfo

from . import geocode
from .alerts import parse_alert
from .ambient import amb_entries, amb_featured
from .clock import TSPANS, parse_goto
from .places import make_city, refresh_results
from .state import WORK_PRESETS
from .themes import C, THEME_ORDER, apply_theme
from .worldmap import ZOOMS, zoom_map


def goto_tz(st):
    if st.home:
        try:
            return ZoneInfo(st.home["zone"])
        except Exception:
            pass
    return st.rows()[st.cursor()].tz


def handle_key(st, k, live, now):
    """Mutates state; returns True to quit."""
    if st.ambient:
        n = len(amb_entries(st))
        cur = amb_featured(st, n, live)
        if k in ("\x03", "q", "Q"):
            return True
        if k in ("V", "v", "\x1b"):
            st.ambient = False
        elif k in ("\x1b[C", "l", "\x1b[B", "j"):
            st.amb_pin = (cur + 1) % n
        elif k in ("\x1b[D", "h", "\x1b[A", "k"):
            st.amb_pin = (cur - 1) % n
        elif k in (" ", "a"):
            st.amb_pin = None
        elif k in ("m", "M"):
            st.amb_drift = not st.amb_drift
        elif k == "T":
            apply_theme(THEME_ORDER[(THEME_ORDER.index(C.name) + 1) % len(THEME_ORDER)])
            st.save()
        return False
    if st.mode in ("help", "radar"):
        st.mode = None
        return False
    if st.mode == "alerts":
        if k in ("\x1b", "A", "q", "\x03"):
            st.mode = None
        elif k in ("\x1b[A", "k"):
            st.aidx = max(0, st.aidx - 1)
        elif k in ("\x1b[B", "j"):
            st.aidx = min(len(st.alerts) - 1, st.aidx + 1) if st.alerts else 0
        elif k in ("n", "N", "a"):
            st.mode, st.buf, st.err = "alertnew", "", ""
        elif k in ("d", "x", "\x1b[3~") and st.alerts:
            st.alerts.pop(st.aidx)
            st.aidx = min(st.aidx, max(0, len(st.alerts) - 1))
            st.save()
        return False
    if st.mode in ("add", "goto", "alertnew"):
        if k in ("\x1b", "\x03"):
            st.mode = "alerts" if st.mode == "alertnew" else None
            return False
        if k in ("\x7f", "\b"):
            st.buf = st.buf[:-1]
        elif k in ("\x15", "\x17"):
            st.buf = ""
        elif st.mode == "add" and k in ("\x1b[A", "\x1b[B"):
            if st.results:
                st.ridx = (st.ridx + (-1 if k.endswith("A") else 1)) % len(st.results)
            return False
        elif k in ("\r", "\n"):
            if st.mode == "add":
                if st.results:
                    e = st.results[st.ridx]
                    if any(c.zone == e["zone"] and c.name.lower() == e["name"].lower() for c in st.cities):
                        st.say("%s is already in the list" % e["name"], C.AMBER)
                    else:
                        try:
                            st.cities.append(make_city(e, st.cities))
                            st.sel = len(st.cities) - 1
                            st.save()
                            st.say("Added %s" % e["name"], C.GREEN)
                        except Exception:
                            st.say("Couldn't load zone %s" % e["zone"], C.RED)
                    st.mode = None
            elif st.mode == "goto":
                t, err = parse_goto(st.buf, goto_tz(st), now)
                if err:
                    st.err = err
                else:
                    st.frozen = t
                    st.mode = None
            else:
                a, err = parse_alert(st.buf, st)
                if err:
                    st.err = err
                else:
                    st.alerts.append(a)
                    st.aidx = len(st.alerts) - 1
                    st.save()
                    st.mode = "alerts"
            return False
        elif len(k) == 1 and k >= " " and k != "\x7f":
            st.buf += k
            st.err = ""
        if st.mode == "add":
            geocode.ensure_geo(st.buf)
            refresh_results(st)
        return False
    # normal mode
    m = re.fullmatch(r"\x1b\[(?:1;(\d))?([A-D])", k)
    mod, letter = (m.group(1), m.group(2)) if m else (None, None)

    def shift(minutes):
        base = st.frozen or live.replace(second=0, microsecond=0)
        st.frozen = base + dt.timedelta(minutes=minutes)

    rows = st.rows()
    n = len(rows)
    cur = st.cursor()
    if k in ("q", "Q", "\x03"):
        return True
    if letter in ("C", "D") or k in ("l", "h"):
        d = 1 if (letter == "C" or k == "l") else -1
        shift(d * (1440 if mod in ("5", "3", "7") else 60 if mod else 15))
    elif k == "\x1b[5~":
        shift(-1440)
    elif k == "\x1b[6~":
        shift(1440)
    elif (letter in ("A", "B") and mod) or k in ("K", "J"):
        if st.markets:
            st.say("The exchange list is fixed. Press M to go back to your cities.", C.AMBER)
        else:
            d = -1 if (letter == "A" or k == "K") else 1
            j = st.sel + d
            if 0 <= j < n:
                st.cities[st.sel], st.cities[j] = st.cities[j], st.cities[st.sel]
                st.sel = j
                st.save()
    elif letter == "A" or k == "k":
        st.set_cursor((cur - 1) % n)
    elif letter == "B" or k == "j":
        st.set_cursor((cur + 1) % n)
    elif k in ("\r", "\n"):
        st.focus = not st.focus
    elif k == "t":
        st.h12 = not st.h12
        st.save()
    elif k in ("r", "R", "n", "\x1b[H", "\x1b[1~"):
        st.frozen = None
    elif k == "m":
        if st.markets:
            st.say("The 'Open' row is always on in the exchange view", C.DIM)
        else:
            st.overlap = not st.overlap
            st.save()
    elif k in ("w",):
        i = WORK_PRESETS.index(st.work) if st.work in WORK_PRESETS else -1
        st.work = WORK_PRESETS[(i + 1) % len(WORK_PRESETS)]
        st.save()
        st.say("Working hours %02d:00–%02d:00" % st.work, C.TEXT)
    elif k in ("a", "/"):
        if st.markets:
            st.say("Press M to go back to your cities first", C.AMBER)
        else:
            st.mode, st.buf, st.results, st.ridx = "add", "", [], 0
    elif k in ("g", "G"):
        st.mode, st.buf, st.err = "goto", "", ""
    elif k in ("d", "x", "\x1b[3~"):
        if st.markets:
            st.say("The exchange list is fixed. Press M to go back to your cities.", C.AMBER)
        elif n <= 1:
            st.say("Can't remove the last city", C.AMBER)
        else:
            gone = st.cities.pop(st.sel)
            if st.home and st.home["zone"] == gone.zone and st.home["name"] == gone.name:
                st.home = None
            st.sel = min(st.sel, len(st.cities) - 1)
            st.save()
            st.say("Removed %s" % gone.name, C.TEXT)
    elif k == "*":
        if st.markets:
            st.say("Press M to go back to your cities to set home", C.AMBER)
        else:
            c = st.cities[st.sel]
            if st.home and st.home["zone"] == c.zone and st.home["name"] == c.name:
                st.home = None
                st.say("Home cleared (comparing with your system zone)", C.TEXT)
            else:
                st.home = {"name": c.name, "zone": c.zone}
                st.say("Home is now %s" % c.name, C.GREEN)
            st.save()
    elif k == "M":
        st.markets = not st.markets
        st.focus = False
        st.say("Exchange view (weekends only; holidays not modelled)" if st.markets else "Back to your cities", C.TEXT)
    elif k == "D":
        if st.markets:
            st.say("Press M to go back to your cities first", C.AMBER)
        else:
            st.mode = "radar"
    elif k == "A":
        st.mode = "alerts"
        st.aidx = min(st.aidx, max(0, len(st.alerts) - 1))
    elif k == "W":
        st.weather = {"off": "c", "c": "f", "f": "off"}[st.weather]
        st.save()
        st.say("Weather " + ("off" if st.weather == "off" else "°" + st.weather.upper() + " (Open-Meteo, needs network)"), C.TEXT)
    elif k == "c":
        st.compact = {"auto": "on", "on": "off", "off": "auto"}[st.compact]
        st.save()
        st.say({"on": "Compact layout", "off": "Full layout", "auto": "Layout: automatic"}[st.compact], C.TEXT)
    elif k in ("+", "=", "-", "_"):
        rows = st.rows()
        if not zoom_map(st, rows, 1 if k in "+=" else -1):
            st.say("Map zoom limit", C.DIM)
        else:
            st.say("Map zoom %d\u00d7" % ZOOMS[st.mzi], C.TEXT)
    elif k in ("]", "["):
        n = max(0, min(len(TSPANS) - 1, st.tsi + (1 if k == "]" else -1)))
        st.tsi = n
        st.say("Timeline: %gh window" % TSPANS[n], C.TEXT)
    elif k == "0":
        st.mzi, st.tsi, st.mcenter = 0, 0, None
        st.say("Zoom reset", C.TEXT)
    elif k == "Z":
        st.wheel = "scrub" if st.wheel == "zoom" else "zoom"
        st.save()
        st.say("Wheel: " + ("zoom map / timeline" if st.wheel == "zoom" else "scrub time / move selection"), C.TEXT)
    elif k in ("V", "v"):
        st.ambient, st.amb_pin, st.amb_t0 = True, None, time.time()
    elif k == "T":
        apply_theme(THEME_ORDER[(THEME_ORDER.index(C.name) + 1) % len(THEME_ORDER)])
        st.save()
        st.say("Theme: " + C.name, C.TEXT)
    elif k == "?":
        st.mode = "help"
    return False


def handle_mouse(st, meta, b, x, y, press, live, now):
    """SGR mouse event. x, y are 0-based. Returns nothing; mutates state."""
    if st.mode or st.ambient:
        return
    wheel = b & 64
    if wheel:
        up = (b & 1) == 0
        bars = meta.get("bars")
        mp = meta.get("map")
        if st.wheel == "zoom" and mp and mp[0] <= x < mp[0] + mp[2] and mp[1] <= y < mp[1] + mp[3]:
            zoom_map(st, st.rows(), 1 if up else -1, ((x - mp[0] + 0.5) / mp[2], (y - mp[1] + 0.5) / mp[3]))
            return
        if bars and bars[0] <= x < bars[0] + bars[1] and y >= bars[2] - 1:
            if st.wheel == "zoom":
                st.tsi = max(0, min(len(TSPANS) - 1, st.tsi + (1 if up else -1)))
            else:
                base = st.frozen or live.replace(second=0, microsecond=0)
                st.frozen = base + dt.timedelta(minutes=-15 if up else 15)
            return
        n = len(st.rows())
        st.set_cursor((st.cursor() + (-1 if up else 1)) % n)
        return
    if not (b & 32) and not press:
        st.drag = None
    if (b & 3) != 0:      # only the left button
        return
    drag = bool(b & 32)
    chip = meta.get("chip")
    bars = meta.get("bars")
    if press and not drag and y == 0 and chip and chip[0] <= x < chip[0] + chip[1]:
        st.frozen = None
        return
    mp = meta.get("map")
    if st.drag and drag:
        kind, x0, y0, base = st.drag
        if kind == "bars":
            xb, nb, _, _, wstart, wspan = bars
            st.frozen = (base - dt.timedelta(minutes=(x - x0) * wspan * 60 / nb)).replace(microsecond=0)
        elif kind == "map" and mp:
            clat, clon = base
            st.mcenter = (max(-80, min(85, clat + (y - y0) * mp[7] / mp[3])),
                          ((clon - (x - x0) * mp[5] / mp[2] + 180) % 360) - 180)
        return
    if bars:
        xb, nb, ytop, ybot, wstart, wspan = bars
        if xb <= x < xb + nb and ytop <= y < ybot:
            idx = meta["rows"].get(y)
            if wspan < 24:
                if press and not drag:
                    st.drag = ("bars", x, y, st.frozen or live.replace(second=0, microsecond=0))
                    if idx is not None:
                        st.set_cursor(idx)
                return
            mins = int(round(((x - xb + 0.5) / nb) * 1440 / 5)) * 5
            st.frozen = wstart + dt.timedelta(minutes=min(1439, mins))
            if idx is not None and press and not drag:
                st.set_cursor(idx)
            return
    if not press or drag:
        return
    idx = meta["rows"].get(y)
    if idx is not None and x < (bars[0] if bars else 999):
        st.set_cursor(idx)
        return
    for i, mx, my, rect in meta["markers"]:
        if (abs(x - mx) <= 1 and y == my) or (rect[0] <= x < rect[2] and rect[1] <= y < rect[3]):
            st.set_cursor(i)
            return
    if mp and mp[0] <= x < mp[0] + mp[2] and mp[1] <= y < mp[1] + mp[3] and ZOOMS[st.mzi] > 1:
        st.drag = ("map", x, y, (mp[6] - mp[7] / 2, mp[4]))
