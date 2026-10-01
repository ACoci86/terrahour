"""Pop-up panels: add city, go to time, help, DST radar, alerts and the alert banner."""
import time
from zoneinfo import ZoneInfo

from .clock import dst_gap_change, dur, fmt_off, fmt_rel, next_transition, ref_offset
from .geocode import geo_status
from .themes import C


def box(cv, x, y, w, h, title):
    for yy in range(y, y + h):
        cv.fill(x, yy, w, C.PANEL_BG)
    cv.put(x, y, "╭" + "─" * (w - 2) + "╮", C.FRAME, C.PANEL_BG)
    cv.put(x, y + h - 1, "╰" + "─" * (w - 2) + "╯", C.FRAME, C.PANEL_BG)
    for yy in range(y + 1, y + h - 1):
        cv.put(x, yy, "│", C.FRAME, C.PANEL_BG)
        cv.put(x + w - 1, yy, "│", C.FRAME, C.PANEL_BG)
    cv.put(x + 2, y, " %s " % title, C.WHITE, C.PANEL_BG, True)


def input_line(cv, x, y, buf):
    cv.put(x, y, "› ", C.ACC1, C.PANEL_BG, True)
    cv.put(x + 2, y, buf, C.WHITE, C.PANEL_BG, True)
    cv.put(x + 2 + len(buf), y, "▏", C.WHITE, C.PANEL_BG, True)


def draw_add(cv, W, H, st, now):
    w = min(72, W - 4)
    h = 14
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    box(cv, x, y, w, h, "Add city")
    input_line(cv, x + 3, y + 2, st.buf)
    cv.put(x + 2, y + 3, "\u2500" * (w - 4), C.BORDER, C.PANEL_BG)
    if not st.buf.strip():
        cv.put(x + 3, y + 5, "Type any city, a country or a zone name:", C.DIM, C.PANEL_BG)
        cv.put(x + 3, y + 6, "naples \u00b7 new zealand \u00b7 Asia/Tokyo \u00b7 springfield", C.KEY, C.PANEL_BG)
        cv.put(x + 3, y + 8, "About 6,000 big cities are built in; any other city is looked up online.", C.DIM, C.PANEL_BG)
    elif not st.results:
        cv.put(x + 3, y + 5, "No match yet." if geo_status(st.buf).startswith("search") else
               "No match. Check the spelling, or try a zone like Europe/Berlin.", C.AMBER, C.PANEL_BG)
    for i, e in enumerate(st.results):
        yy = y + 4 + i
        sel = i == st.ridx
        bg = C.SEL_BG if sel else C.PANEL_BG
        cv.fill(x + 1, yy, w - 2, bg)
        try:
            off = fmt_off(now.astimezone(ZoneInfo(e["zone"])).utcoffset())
        except Exception:
            off = ""
        cv.put(x + 3, yy, "\u25b8" if sel else " ", C.ACC1, bg, True)
        cv.put(x + 5, yy, e["name"][:18], C.WHITE if sel else C.TEXT, bg, sel)
        cv.put(x + 24, yy, (e.get("country") or "")[:18], C.DIM, bg)
        cv.put(x + 43, yy, e["zone"][:16], C.DIM, bg)
        cv.put(x + w - 3 - len(off), yy, off, C.CYAN, bg)
    cv.put(x + 3, y + h - 2, "\u2191\u2193 choose   Enter add   Esc cancel", C.DIM, C.PANEL_BG)
    gs = geo_status(st.buf)
    if gs:
        cv.put(x + w - 3 - len(gs), y + h - 2, gs, C.AMBER if "unavailable" in gs else C.DIM, C.PANEL_BG)


def goto_zone_name(st):
    return st.home["name"] if st.home else st.rows()[st.cursor()].name


def draw_goto(cv, W, H, st):
    w = min(68, W - 4)
    h = 8
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    box(cv, x, y, w, h, "Go to time")
    input_line(cv, x + 3, y + 2, st.buf)
    if st.err:
        cv.put(x + 3, y + 3, st.err, C.RED, C.PANEL_BG)
    cv.put(x + 3, y + 4, "15:30  or  3pm  → local time in %s" % goto_zone_name(st)[:20], C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + 5, "15:30z → UTC   +2h / -45m / +1d → relative   2026-10-05 09:00", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + h - 2, "Enter go   empty = back to live   Esc cancel", C.DIM, C.PANEL_BG)


HELP_L = [
    ("← →", "scrub time 15 min"),
    ("Shift ← →", "scrub 1 hour"),
    ("PgUp PgDn", "scrub 1 day"),
    ("g", "go to a time"),
    ("r  Home", "back to live"),
    ("↑ ↓  j k", "select row"),
    ("Shift ↑ ↓  J K", "move city up / down"),
    ("a", "add a city"),
    ("d  Del  x", "remove city"),
    ("Enter", "focus selected row"),
    ("*", "set / clear home city"),
    ("m", "overlap row on / off"),
    ("w", "cycle working hours"),
]


HELP_R = [
    ("M", "stock-exchange view"),
    ("D", "DST radar"),
    ("A", "alerts (bell + popup)"),
    ("W", "weather off / °C / °F"),
    ("T", "next theme"),
    ("c", "compact layout on / off / auto"),
    ("V", "ambient screensaver view"),
    ("t", "12h / 24h clock"),
    ("click", "select a row or map city"),
    ("click bars", "jump to that time"),
    ("drag bars", "scrub time"),
    ("wheel", "zoom map / timeline (Z: scrub)"),
    ("+ -", "zoom map"),
    ("[ ]", "zoom timeline"),
    ("0", "reset zoom"),
    ("Z", "wheel: zoom / scrub"),
    ("drag map", "pan when zoomed"),
    ("click LIVE", "back to live"),
    ("?", "this help"),
    ("q  Ctrl-C", "quit"),
]


def draw_help(cv, W, H):
    w = min(100, W - 4)
    two = w >= 84
    items = HELP_L + HELP_R if not two else None
    h = (max(len(HELP_L), len(HELP_R)) if two else len(items)) + 4
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    box(cv, x, y, w, h, "Keys")
    if two:
        for col, lst in enumerate((HELP_L, HELP_R)):
            cx = x + 3 + col * (w // 2 - 1)
            for i, (k, d) in enumerate(lst):
                cv.put(cx, y + 2 + i, k, C.KEY, C.PANEL_BG, True)
                cv.put(cx + 20, y + 2 + i, d, C.TEXT, C.PANEL_BG)
    else:
        for i, (k, d) in enumerate(items):
            cv.put(x + 3, y + 2 + i, k, C.KEY, C.PANEL_BG, True)
            cv.put(x + 24, y + 2 + i, d, C.TEXT, C.PANEL_BG)
    cv.put(x + 3, y + h - 1, " any key to close ", C.DIM, C.PANEL_BG)


def draw_radar(cv, W, H, st, now):
    cities = st.cities
    n = len(cities)
    w = min(104, W - 4)
    vis = min(n, max(3, H - 12))
    h = vis + 7
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    ref = "home" if st.home else "here"
    box(cv, x, y, w, h, "DST radar  ·  next clock change, and gap to %s" % ref)
    cv.put(x + 3, y + 2, "City", C.DIM, C.PANEL_BG)
    cv.put(x + 20, y + 2, "Now", C.DIM, C.PANEL_BG)
    cv.put(x + 30, y + 2, "Next clock change", C.DIM, C.PANEL_BG)
    cv.put(x + 66, y + 2, "Gap to " + ref, C.DIM, C.PANEL_BG)
    top = max(0, min(st.sel - vis // 2, n - vis))
    for k in range(vis):
        i = top + k
        c = cities[i]
        yy = y + 3 + k
        bg = C.SEL_BG if i == st.sel else C.PANEL_BG
        cv.fill(x + 1, yy, w - 2, bg)
        cv.put(x + 3, yy, "● ", c.color, bg)
        cv.put(x + 5, yy, c.name[:14], c.color, bg, i == st.sel)
        cv.put(x + 20, yy, fmt_off(now.astimezone(c.tz).utcoffset()), C.TEXT, bg)
        tr = next_transition(c.tz, now)
        if tr:
            days = (tr[0] - now).days
            loc = tr[0].astimezone(c.tz)
            sign = "+" if tr[2] > tr[1] else "-"
            dl = abs((tr[2] - tr[1]).total_seconds()) / 3600
            cv.put(x + 30, yy, "%s %s  %s%gh  in %dd" % (loc.strftime("%a %d %b"), loc.strftime("%H:%M"), sign, dl, days),
                   C.AMBER if days <= 30 else C.TEXT, bg)
        else:
            cv.put(x + 30, yy, "no changes ahead", C.DIM, bg)
        g = dst_gap_change(c, st, now)
        gnow = c.info(now)[1] - ref_offset(st, now)
        if g:
            cv.put(x + 66, yy, "%s → %s  %s" % (fmt_rel(g[1]), fmt_rel(g[2]), g[0].astimezone(c.tz).strftime("%d %b")),
                   C.AMBER, bg, True)
        else:
            cv.put(x + 66, yy, fmt_rel(gnow) + "  steady", C.DIM, bg)
    cv.put(x + 3, y + h - 2, "A gap that changes means your usual meeting time shifts by an hour. "
                             "* sets home. any key closes", C.DIM, C.PANEL_BG)


def alert_desc(a):
    if a["kind"] == "time":
        return "%02d:%02d daily · %s" % (a["m"] // 60, a["m"] % 60, a["name"])
    if a["kind"] == "timer":
        left = max(0, int(a["at"] - time.time()))
        return "timer \u00b7 fires in " + (dur(left // 60) if left >= 60 else "%ds" % left)
    return "when %s %s" % (a["name"], "opens" if a["kind"] == "open" else "closes")


def draw_alerts(cv, W, H, st):
    w = min(76, W - 4)
    h = max(10, min(len(st.alerts), 10) + 8)
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    box(cv, x, y, w, h, "Alerts")
    if not st.alerts:
        cv.put(x + 3, y + 2, "No alerts yet. Press n to add one.", C.DIM, C.PANEL_BG)
    for i, a in enumerate(st.alerts[:10]):
        yy = y + 2 + i
        bg = C.SEL_BG if i == st.aidx else C.PANEL_BG
        cv.fill(x + 1, yy, w - 2, bg)
        cv.put(x + 3, yy, "♪", C.AMBER, bg, True)
        cv.put(x + 5, yy, alert_desc(a)[:w - 8], C.WHITE if i == st.aidx else C.TEXT, bg)
    cv.put(x + 3, y + h - 4, "Rings the bell and shows a notification while terrahour is open.", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + h - 2, "n new   d delete   ↑↓ select   Esc close", C.DIM, C.PANEL_BG)


def draw_alertnew(cv, W, H, st):
    w = min(72, W - 4)
    h = 11
    x, y = (W - w) // 2, max(1, (H - h) // 3)
    box(cv, x, y, w, h, "New alert")
    input_line(cv, x + 3, y + 2, st.buf)
    if st.err:
        cv.put(x + 3, y + 3, st.err, C.RED, C.PANEL_BG)
    cv.put(x + 3, y + 4, "9am tokyo       every day at 09:00 in Tokyo", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + 5, "open new york   when New York's working day starts", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + 6, "close NYSE      when that exchange closes", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + 7, "in 25m          one-off timer", C.DIM, C.PANEL_BG)
    cv.put(x + 3, y + h - 2, "Enter create   Esc cancel", C.DIM, C.PANEL_BG)


def draw_banner(cv, W, st):
    text, until = st.banner
    if not text or time.time() > until:
        return
    t = "  ♪  %s  " % text
    w = min(W - 4, len(t) + 2)
    x = (W - w) // 2
    for yy in (2, 3, 4):
        cv.fill(x, yy, w, C.AMBER)
    cv.put(x + 1, 3, t[:w - 2], C.BG, C.AMBER, True)


def draw_overlays(cv, W, H, st, now):
    cv.meta["mode"] = st.mode
    if st.mode == "add":
        draw_add(cv, W, H, st, now)
    elif st.mode == "goto":
        draw_goto(cv, W, H, st)
    elif st.mode == "help":
        draw_help(cv, W, H)
    elif st.mode == "radar":
        draw_radar(cv, W, H, st, now)
    elif st.mode == "alerts":
        draw_alerts(cv, W, H, st)
    elif st.mode == "alertnew":
        draw_alertnew(cv, W, H, st)
    draw_banner(cv, W, st)
