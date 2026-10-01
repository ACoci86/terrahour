"""The ambient (screensaver) view: a big clock over the map, cycling through your cities."""
import time

from .astro import daylight, sun_pos
from .canvas import Canvas
from .clock import fmt_clock, fmt_off, local_zone, utcnow
from .draw import draw_map
from .places import ABBR
from .themes import C, mix


AMB_FONT = {
    "0": ("███", "█ █", "█ █", "█ █", "███"), "1": (" █ ", "██ ", " █ ", " █ ", "███"),
    "2": ("███", "  █", "███", "█  ", "███"), "3": ("███", "  █", "███", "  █", "███"),
    "4": ("█ █", "█ █", "███", "  █", "  █"), "5": ("███", "█  ", "███", "  █", "███"),
    "6": ("███", "█  ", "███", "█ █", "███"), "7": ("███", "  █", "  █", "  █", "  █"),
    "8": ("███", "█ █", "███", "█ █", "███"), "9": ("███", "█ █", "███", "  █", "███"),
    ":": (" ", "█", " ", "█", " "), " ": ("  ", "  ", "  ", "  ", "  "),
}


AMB_CYCLE = 12          # seconds each city stays featured
AMB_DRIFT = 4.0         # seconds per map dot of rotation


def big_text(s, wide):
    out = [""] * 5
    for n, ch in enumerate(s):
        g = AMB_FONT.get(ch, AMB_FONT[" "])
        for i in range(5):
            r = g[i]
            if wide:
                r = "".join(c * 2 for c in r)
            out[i] += r + ("" if n == len(s) - 1 else " ")
    return out


def amb_entries(st, now=None):
    """Rotation list for the ambient view: this computer's own time first, then every city.
    Each entry is (label, tz, colour, lat, lon, row index or -1). The first one takes its offset straight from the
    operating system's clock, so it is right whatever the zone name says."""
    rows = st.rows()
    lz = local_zone()
    key = getattr(lz, "key", None) or ""
    sys_tz = (now or utcnow()).astimezone().tzinfo       # fixed offset as the OS reports it at this instant
    off = sys_tz.utcoffset(None).total_seconds() / 3600
    label = key.split("/")[-1].replace("_", " ") if key else "This computer"
    ents = [(c.name, c.tz, c.color, c.lat, c.lon, i) for i, c in enumerate(rows)]
    match = next((i for i, c in enumerate(rows) if key and c.zone == key), None)
    if match is not None:
        c = rows[match]
        ents.pop(match)
        ents.insert(0, (c.name, sys_tz, c.color, c.lat, c.lon, match))
    else:
        ents.insert(0, (label, sys_tz, C.CYAN, 40.0, off * 15.0, -1))
    return ents


def amb_featured(st, n, live_now):
    if st.amb_pin is not None:
        return st.amb_pin % n
    e = max(0.0, live_now.timestamp() - st.amb_t0) if st.amb_t0 else 0.0
    if e < 30 or n < 2:                       # this computer's own time first, for half a minute
        return 0
    return 1 + int((e - 30) // AMB_CYCLE) % (n - 1)


def compose_ambient(W, H, st, now, live_now):
    cv = Canvas(W, H)
    rows = st.rows()
    infos = [c.info(now) for c in rows]
    ents = amb_entries(st, now)
    n = len(ents)
    fe = amb_featured(st, n, live_now)
    label, tz, col, lat, lon, fi = ents[fe]
    loc = now.astimezone(tz)
    off = loc.utcoffset()
    abbr = loc.tzname() or ""
    if abbr[:1] in "+-" or not abbr:
        abbr = ABBR.get(getattr(tz, "key", ""), abbr)
    wide = W >= 66
    block_h = 8
    mh = min(H - block_h - 1, int(W / 5.14 * 1.3))      # fill the screen; stretch a little if needed
    use_map = mh >= 6
    total = (mh + 1 if use_map else 0) + block_h
    pad = max(0, (H - total) // 2)
    if use_map:
        mw = W
        dot = 360.0 / (mw * 2)
        st.amb_clon = -(int(live_now.timestamp() / AMB_DRIFT) % (mw * 2)) * dot if st.amb_drift else 0.0
        focus, st.focus = st.focus, False
        draw_map(cv, W, pad, mw, mh, infos, rows, fi, st, now, None)
        st.focus = focus
        y = pad + mh + 1
    else:
        y = pad
    utc_h = now.hour + now.minute / 60 + now.second / 3600
    decl, eot = sun_pos(now)
    day = daylight(lat, lon, utc_h, decl, eot) > 0.5
    sub = "%s  (%s)  ·  %s" % (abbr, fmt_off(off), loc.strftime("%a %d %b"))
    head = ("☼ " if day else "☾ ") + label
    full = len(head) + 3 + len(sub)
    x = max(0, (W - full) // 2)
    cv.put(x, y, head, col, None, True)
    cv.put(x + len(head) + 3, y, sub, C.DIM)
    if st.h12:
        txt = loc.strftime("%I:%M:%S").lstrip("0")
        ap = loc.strftime("%p")
    else:
        txt, ap = loc.strftime("%H:%M:%S"), ""
    lines = big_text(txt, wide)
    bw = len(lines[0])
    bx = max(0, (W - bw - (3 if ap else 0)) // 2)
    gcol, gi = [], 0
    for ch in txt:
        w = len(AMB_FONT[ch][0]) * (2 if wide else 1)
        gcol.extend([gi] * (w + 1))
        gi += 1
    for i, ln in enumerate(lines):
        for j, ch in enumerate(ln):
            if ch != " ":
                f = 1.0 if gcol[j] < len(txt) - 2 else 0.6      # seconds a little softer
                cv.put(bx + j, y + 1 + i, "█", mix(C.BG, col, f))
    if ap:
        cv.put(bx + bw + 1, y + 5, ap, C.DIM)
    # strip with every entry's time, starting at the featured one
    segs = []
    for k in range(n):
        e = ents[(fe + k) % n]
        segs.append(((fe + k) % n, e[0], fmt_clock(now.astimezone(e[1]), st.h12), e[2]))
    fit, wsum = [], 0
    for sg in segs:
        w = len(sg[1]) + 1 + len(sg[2]) + 3
        if wsum + w - 3 > W - 4:
            break
        fit.append(sg)
        wsum += w
    sx = max(0, (W - (wsum - 3)) // 2)
    for i, name, t, ccol in fit:
        feat = i == fe
        cv.put(sx, y + 7, name, ccol if feat else mix(C.BG, ccol, 0.55), None, feat)
        cv.put(sx + len(name) + 1, y + 7, t, C.WHITE if feat else C.DIM, None, feat)
        sx += len(name) + len(t) + 4
    hint = "" if time.time() - st.amb_t0 > 6 else "V exit  ·  ← → city  ·  space auto  ·  m drift  ·  T theme  ·  q quit"
    if hint and len(hint) < W - 2:
        cv.put(max(0, (W - len(hint)) // 2), y + 6, hint, mix(C.BG, C.DIM, 0.6))
    text, until = st.banner if st.banner else ("", 0)
    if text and time.time() < until:
        t = " %s " % text
        cv.put(max(0, (W - len(t)) // 2), 0, t, C.AMBER, C.SEL_BG, True)
    return cv
