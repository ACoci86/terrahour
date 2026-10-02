"""Choose a layout for the terminal size and draw one full frame into a Canvas."""
import datetime as dt
import time

from .ambient import compose_ambient
from .astro import daylight, sun_pos
from .canvas import Canvas
from .clock import (fmt_delta, fmt_off, is_open, overlap_window, status_info, time_window, work_alpha)
from .draw import draw_details, draw_footer, draw_map, draw_table, draw_ticks, draw_topbar
from .overlays import draw_overlays
from .themes import C, mix
from .weather import weather_refresh

MAP_MIN_H = 8       # rows; below this the map is not worth drawing


def is_compact(st, W, H):
    if st.compact == "on":
        return True
    if st.compact == "off":
        return False
    return W < 76 or H < min(len(st.rows()), 9) + 7


def compact_clock(loc, h12):
    if h12:
        return loc.strftime("%I:%M%p").lstrip("0")[:-1].lower()      # 3:20p
    return loc.strftime("%H:%M")


def compose_compact(W, H, st, now, live_now):
    """Small-pane layout: no map, no frame, one line per city. Meant for tmux splits and narrow windows."""
    cv = Canvas(W, H)
    rows = st.rows()
    n = len(rows)
    sel = min(st.cursor(), n - 1)
    if st.weather != "off":
        weather_refresh(rows)
    infos = [c.info(now) for c in rows]
    # --- slim top bar
    cv.fill(0, 0, W, C.TOP_BG)
    chip = "⏸ " + fmt_delta((now - live_now).total_seconds()) if st.frozen else "● LIVE"
    chip_col = C.AMBER if st.frozen else C.GREEN
    cx = max(0, W - 1 - len(chip))
    cv.put(cx, 0, chip, chip_col, C.TOP_BG, True)
    cv.meta["chip"] = (cx, len(chip))
    clock = now.strftime("%H:%M") + " UTC"
    tx = cx - 2 - len(clock)
    if tx > 1:
        cv.put(tx, 0, clock, C.CYAN, C.TOP_BG, True)
    if tx > 18:
        cv.put(1, 0, "terra", C.WHITE, C.TOP_BG, True)
        for i, c in enumerate("hour"):
            cv.put(6 + i, 0, c, mix(C.ACC1, C.ACC2, i / 3), C.TOP_BG, True)
        if st.markets and tx > 30:
            cv.put(12, 0, "markets", C.DIM, C.TOP_BG)
    # --- vertical budget
    foot_y = H - 1 if H >= 10 else None
    det_y = (H - 2 if foot_y is not None else H - 1) if H >= 6 else None
    y_end = H - (1 if foot_y is not None else 0) - (1 if det_y is not None else 0)
    # --- columns
    nw = min(14, max(len(c.name) for c in rows))
    show_glyph = True

    def geometry():
        xt = 4 + nw + 1
        xb = xt + 8 + (2 if show_glyph else 1)
        return xt, xb, W - 1 - xb
    xt, xb, nb = geometry()
    while nb < 14 and nw > 6:
        nw -= 1
        xt, xb, nb = geometry()
    if nb < 14 and show_glyph:
        show_glyph = False
        xt, xb, nb = geometry()
    bars_on = nb >= 8
    ticks = bars_on and nb >= 20 and (y_end - 2) >= 2
    y0 = 2 if ticks else 1
    region = max(1, y_end - y0)
    ov = (st.markets or st.overlap) and n >= 2 and region >= 4
    vis = max(1, min(n, region - (1 if ov else 0)))
    top = max(0, min(sel - vis // 2, n - vis))
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    wstart, wspan = time_window(st, now)
    frac = (now - wstart).total_seconds() / (wspan * 3600)
    nowc = xb + min(max(nb, 1) - 1, max(0, int(frac * max(nb, 1))))
    ws, we = st.work
    mk = st.markets
    # --- hour ticks
    if ticks:
        draw_ticks(cv, 1, xb, nb, wstart, wspan, step24=3 if nb >= 40 else 6)
        if cv.ch[1][nowc] == " ":
            cv.put(nowc, 1, "▼", C.WHITE, None, True)
        if n > vis:
            cv.put(1, 1, "%d/%d" % (sel + 1, n), C.DIM)
    # --- rows
    insts = [wstart + dt.timedelta(hours=(j + 0.5) * wspan / nb) for j in range(nb)] if bars_on else []
    min_alpha = [1.0] * nb
    open_count = [0] * nb
    for i in range(n):
        ci = rows[i]
        alphas = []
        for j in range(nb if bars_on else 0):
            lh = insts[j].astimezone(ci.tz)
            if ci.sessions:
                o = is_open(ci, lh, st.work)
                alphas.append(1.0 if o else 0.12)
                open_count[j] += 1 if o else 0
            else:
                alphas.append(work_alpha(lh.hour + lh.minute / 60, ws, we))
            min_alpha[j] = min(min_alpha[j], alphas[j])
        if not (top <= i < top + vis):
            continue
        y = y0 + (i - top)
        cv.meta["rows"][y] = i
        loc, off, abbr = infos[i]
        is_sel = i == sel
        rbg = C.SEL_BG if is_sel else None
        if is_sel:
            cv.fill(0, y, W, C.SEL_BG)
        cv.put(1, y, "▸" if is_sel else " ", ci.color, rbg, True)
        cv.put(2, y, "●", ci.color, rbg)
        nm = ci.name if len(ci.name) <= nw else ci.name[:nw - 1] + "…"
        cv.put(4, y, nm, ci.color, rbg, is_sel)
        opened = is_open(ci, loc, st.work)
        cv.put(xt, y, compact_clock(loc, st.h12), C.WHITE if opened else C.DIM, rbg, opened)
        d = (loc.date() - now.date()).days
        if d:
            cv.put(xt + 6, y, "%+d" % d, C.AMBER, rbg, True)
        if show_glyph:
            day = daylight(ci.lat, ci.lon, now.hour + now.minute / 60, *sun_pos(now)) > 0.5
            cv.put(xt + 8, y, "☼" if day else "☾", C.SUN if day else C.MOON, rbg)
        if bars_on:
            for j in range(nb):
                a = alphas[j] * (0.5 if st.focus and not is_sel else 1.0)
                colr = mix(C.BAR_BG, ci.color, a)
                if xb + j == nowc:
                    cv.put(xb + j, y, "┆", C.WHITE, colr, True)
                else:
                    cv.put(xb + j, y, " ", None, colr)
        else:
            cv.put(xt + 9, y, fmt_off(off).replace("UTC", ""), C.DIM, rbg)
    yy = y0 + vis
    if ov:
        oc = C.GREEN
        cv.put(2, yy, "▍", oc)
        cv.put(4, yy, "Open" if mk else ("Overlap" if nw >= 7 else "Shared"), oc, None, True)
        if mk:
            k = sum(1 for c in rows if status_info(c, now, st.work)[0])
            cv.put(xt, yy, "%d/%d" % (k, n), oc)
        else:
            win = overlap_window(rows, day0, ws, we)
            cv.put(xt, yy, "none" if win is None else "%02d-%02dz" % (win[0] // 60, (win[1] // 60) % 24), oc if win else C.DIM)
        if bars_on:
            for j in range(nb):
                a = (open_count[j] / n) if mk else (min_alpha[j] if min_alpha[j] >= 0.99 else min_alpha[j] * 0.35)
                colr = mix(C.BAR_BG, oc, a)
                if xb + j == nowc:
                    cv.put(xb + j, yy, "┆", C.WHITE, colr, True)
                else:
                    cv.put(xb + j, yy, " ", None, colr)
    if bars_on:
        cv.meta["bars"] = (xb, nb, y0, y0 + vis + (1 if ov else 0), wstart, wspan)
    # --- bottom lines
    if det_y is not None:
        draw_details(cv, W, det_y, st, infos, rows, sel, now)
    if foot_y is not None:
        x = 2
        for k, d in (("←→", "time"), ("↑↓", "select"), ("c", "full"), ("?", "help"), ("q", "quit")):
            if x + len(k) + len(d) + 3 > W - 2:
                break
            cv.put(x, foot_y, k, C.KEY, None, True)
            cv.put(x + len(k) + 1, foot_y, d, C.DIM)
            x += len(k) + len(d) + 3
        text, col, until = st.msg
        if text and time.time() < until:
            t = " %s " % text
            cv.put(max(0, W - len(t) - 1), foot_y, t, col or C.TEXT, C.SEL_BG, True)
    draw_overlays(cv, W, H, st, now)
    return cv


def compose(W, H, st, now, live_now):
    if st.ambient and W >= 30 and H >= 10:
        return compose_ambient(W, H, st, now, live_now)
    if is_compact(st, W, H):
        return compose_compact(W, H, st, now, live_now)
    cv = Canvas(W, H)
    rows = st.rows()
    sel = min(st.cursor(), len(rows) - 1)
    if st.weather != "off":
        weather_refresh(rows)
    n = len(rows)
    infos = [c.info(now) for c in rows]
    draw_topbar(cv, W, st, now, live_now)
    ov = 1 if ((st.markets or st.overlap) and n >= 2) else 0
    max_vis = max(1, H - 3 - 4 - ov)
    vis = min(n, max_vis)
    # short window: scroll the table rather than lose the map, as long as a few rows stay in view
    room = max_vis - MAP_MIN_H
    if vis > room >= min(n, 5) and int((W - 2) / 5.14) >= MAP_MIN_H:
        vis = room
    top = max(0, min(sel - vis // 2, n - vis))
    table_h = vis + 4 + ov
    avail = H - 1 - table_h - 2
    mh = min(avail, int((W - 2) / 5.14))
    if mh >= MAP_MIN_H:
        mw = min(W - 2, int(mh * 5.14))
        flags = [status_info(c, now, st.work)[0] for c in rows] if st.markets else None
        draw_map(cv, W, 1, mw, mh, infos, rows, sel, st, now, flags)
    else:
        mh = 0
    # the table sits right under the map; rows the map cannot use stay empty above the details line
    draw_table(cv, W, 1 + mh, vis, top, infos, rows, sel, st, now)
    draw_details(cv, W, H - 2, st, infos, rows, sel, now)
    draw_footer(cv, W, H - 1, st)
    draw_overlays(cv, W, H, st, now)
    return cv
