"""Drawing the main screen: top bar, world map, the city table, details line and footer."""
import datetime as dt
import math
import time

from .astro import daylight, sun_pos, sun_times
from .clock import (dst_gap_change, fmt_clock, fmt_delta, fmt_local, fmt_off, fmt_rel, is_open, next_transition,
                    overlap_window, ref_offset, status_info, status_text, time_window, work_alpha)
from .themes import C, mix
from .weather import weather_cell
from .worldmap import ZOOMS, land_cells, map_view


def draw_ticks(cv, y, xb, nb, start, span, step24=2):
    if span >= 24:
        for h in range(0, 25, step24):
            col = xb + round(h * nb / 24)
            lx = xb if h == 0 else (xb + nb - 2 if h == 24 else col - 1)
            cv.put(lx, y, "%02d" % h, C.DIM)
        return
    ivl = {12: 60, 6: 30, 3: 15, 1: 5}.get(int(span), 60)
    t = start.replace(second=0, microsecond=0)
    t += dt.timedelta(minutes=(-(t.hour * 60 + t.minute)) % ivl)
    end = start + dt.timedelta(hours=span)
    last = -9
    while t < end:
        col = xb + int((t - start).total_seconds() / (span * 3600) * nb)
        label = "%02d" % t.hour if ivl % 60 == 0 else "%02d:%02d" % (t.hour, t.minute)
        lx = col - len(label) // 2
        if lx > last + 1 and lx >= xb - 1 and lx + len(label) <= xb + nb + 1:
            cv.put(lx, y, label, C.AMBER if (t.hour == 0 and t.minute == 0) else C.DIM)
            last = lx + len(label)
        t += dt.timedelta(minutes=ivl)


def draw_topbar(cv, W, st, now, live_now):
    cv.fill(0, 0, W, C.TOP_BG)
    cv.put(1, 0, " ◉ ", C.ACC2, C.TOP_BG, True)
    cv.put(4, 0, "terra", C.WHITE, C.TOP_BG, True)
    name = "hour"
    for i, c in enumerate(name):
        cv.put(9 + i, 0, c, mix(C.ACC1, C.ACC2, i / (len(name) - 1)), C.TOP_BG, True)
    bits = ["markets" if st.markets else "work %02d–%02d" % st.work, "12h" if st.h12 else "24h", C.name]
    if st.weather != "off":
        bits.append("°" + st.weather.upper())
    if st.frozen:
        chip = "⏸ %s" % fmt_delta((now - live_now).total_seconds())
        chip_col = C.AMBER
    else:
        chip, chip_col = "● LIVE", C.GREEN
    clock = now.strftime("%H:%M:%S") + " UTC"
    date = now.strftime("%a %d %b %Y")
    x = W - 2 - len(chip)
    cv.put(x, 0, chip, chip_col, C.TOP_BG, True)
    cv.meta["chip"] = (x, len(chip))
    x -= len(clock) + 3
    cv.put(x, 0, clock, C.CYAN, C.TOP_BG, True)
    if x - len(date) - 3 >= 16:
        x -= len(date) + 3
        cv.put(x, 0, date, C.TEXT, C.TOP_BG)
    na = len(st.alerts) + sum(1 for a in st.alerts if False)
    if na and x - len("♪ %d" % na) - 3 >= 16:
        t = "♪ %d" % na
        x -= len(t) + 3
        cv.put(x, 0, t, C.AMBER, C.TOP_BG, True)
    while bits and 16 + len("  ·  ".join(bits)) > x - 2:
        bits.pop()                 # narrow terminal: the settings summary gives way to the clock
    cv.put(16, 0, "  ·  ".join(bits), C.DIM, C.TOP_BG)


def draw_map(cv, W, y0, mw, mh, infos, rows, sel, st, now, open_flags):
    focus = st.focus
    x0 = (W - mw) // 2
    clon, lonspan, ltop, lspan = map_view(st, rows, sel)
    cv.meta["map"] = (x0, y0, mw, mh, clon, lonspan, ltop, lspan)
    grid = land_cells(mw, mh, clon, lonspan, ltop, lspan)
    decl, eot = sun_pos(now)
    utc_h = now.hour + now.minute / 60 + now.second / 3600
    anchors = [(i, (info[1].total_seconds() / 3600) * 15) for i, info in enumerate(infos)]
    for r in range(mh):
        lat = ltop - (r + 0.5) * lspan / mh
        for c in range(mw):
            if not grid[r][c]:
                continue
            lon = ((clon + ((c + 0.5) / mw - 0.5) * lonspan + 180) % 360) - 180
            best = min(anchors, key=lambda a: min(abs(lon - a[1]), 360 - abs(lon - a[1])))[0]
            f = 0.30 + 0.70 * daylight(lat, lon, utc_h, decl, eot)
            if focus and best != sel:
                f *= 0.45
            cv.put(x0 + c, y0 + r, chr(0x2800 + grid[r][c]), mix(C.BG, rows[best].color, f))

    def locate(lat, lon):
        fx = 0.5 + (((lon - clon + 180) % 360) - 180) / lonspan
        fy = (ltop - lat) / lspan
        if 0 <= fx < 1 and 0 <= fy < 1:
            return x0 + int(fx * mw), y0 + int(fy * mh)
        return None

    slon = (-15 * (utc_h + eot / 60 - 12) + 180) % 360 - 180
    p = locate(math.degrees(decl), slon)
    if p:
        cv.put(p[0], p[1], "☼", C.SUN, None, True)
    if ZOOMS[st.mzi] > 1 and not st.ambient:
        cv.put(x0 + 1, y0, "zoom %d×  ·  drag to pan  ·  0 resets" % ZOOMS[st.mzi], C.DIM)
    pts = [locate(ci.lat, ci.lon) for ci in rows]
    placed, chosen_by = [], {}
    for i in sorted(range(len(rows)), key=lambda i: (i != sel, i)):
        if pts[i] is None:
            continue
        ci = rows[i]
        x, y = pts[i]
        _, off, abbr = infos[i]
        sub = "(%s)" % fmt_off(off) if abbr in ("UTC", "") else "%s (%s)" % (abbr, fmt_off(off))
        chosen = None
        # name over zone where there is room, then the name alone, then just the dot: labels never overlap
        for lines, w, cands in (
                (2, max(len(ci.name), len(sub)), [(2, 0), (-1, 0), (2, -2), (-1, -2), (2, 2), (-1, 2),
                                                  (0, -3), (0, 2), (2, -1), (-1, -1)]),
                (1, len(ci.name), [(2, 0), (-1, 0), (2, -1), (-1, -1), (2, 1), (-1, 1), (0, -1), (0, 1)])):
            for side, dy in cands:
                lx, ly = x + {2: 2, -1: -w - 1, 0: -w // 2}[side], y + dy
                if lx < 1 or lx + w >= W - 1 or ly < y0 or ly + lines - 1 >= y0 + mh:
                    continue
                rect = (lx - 1, ly, lx + w + 1, ly + lines)
                if any(not (rect[2] <= q[0] or q[2] <= rect[0] or rect[3] <= q[1] or q[3] <= rect[1]) for q in placed):
                    continue
                if any(rect[0] <= q[0] < rect[2] and rect[1] <= q[1] < rect[3] for q in pts if q):
                    continue
                chosen = (lx, ly, w, lines)
                break
            if chosen:
                break
        if chosen:
            lx, ly, w, lines = chosen
            placed.append((lx - 1, ly, lx + w + 1, ly + lines))
            chosen_by[i] = (lx, ly, w, sub if lines == 2 else None)
    dots = []
    for i, ci in enumerate(rows):
        if pts[i] is None:
            continue
        x, y = pts[i]
        is_sel = i == sel
        dimmed = (focus and not is_sel) or (open_flags is not None and not open_flags[i] and not is_sel)
        col = mix(C.BG, ci.color, 0.45) if dimmed else ci.color
        hit = (x, y, x + 1, y + 1)
        if i in chosen_by:
            lx, ly, w, sub = chosen_by[i]
            hit = (lx - 1, ly, lx + w + 1, ly + (2 if sub else 1))
            for yy in range(ly, hit[3]):
                cv.put(lx - 1, yy, " " * (w + 2))
            cv.put(lx, ly, ci.name, col, None, True)
            if sub:
                cv.put(lx, ly + 1, sub, mix(C.BG, ci.color, 0.35 if dimmed else 0.75))
        cv.meta["markers"].append((i, x, y, hit))
        dots.append((x, y, "◉" if is_sel else "●", C.WHITE if is_sel else col))
    for x, y, ch, col in dots:             # dots last, so no label can cover one
        cv.put(x, y, ch, col, None, True)


def layout(W, weather_on):
    L = {"xn": 3, "xc": 6, "xt": 24, "xg": 37, "xz": 39}
    x = 46
    if W >= 100:
        L["xo"] = x
        x += 11
        L["xr"] = x
        x += 8
    if weather_on and W >= 118:
        L["xw"] = x
        x += 13
    if W >= (136 if weather_on else 125):
        L["xs"] = x
        x += 15
    L["xb"] = x + 1
    return L


def draw_table(cv, W, y0, vis, top, infos, rows, sel, st, now):
    n = len(rows)
    ws, we = st.work
    mk = st.markets
    ov = (mk or st.overlap) and n >= 2
    height = vis + 4 + (1 if ov else 0)
    xl, xr = 1, W - 2
    cv.put(xl, y0, "╭" + "─" * (xr - xl - 1) + "╮", C.BORDER)
    cv.put(xl, y0 + height - 1, "╰" + "─" * (xr - xl - 1) + "╯", C.BORDER)
    for yy in range(y0 + 1, y0 + height - 1):
        cv.put(xl, yy, "│", C.BORDER)
        cv.put(xr, yy, "│", C.BORDER)
    L = layout(W, st.weather != "off")
    xn, xc, xt, xg, xz, xb = L["xn"], L["xc"], L["xt"], L["xg"], L["xz"], L["xb"]
    xe = W - 4
    nb = xe - xb
    if nb < 24:
        cv.put(3, y0 + 1, "terminal too narrow for the timeline", C.DIM)
        return
    ref_label = "vs Home" if st.home else "vs here"
    hy = y0 + 1
    cv.put(xn, hy, "#", C.DIM)
    cv.put(xc, hy, "Exchange" if mk else "City", C.DIM)
    cv.put(xt, hy, "Time (Local)", C.DIM)
    cv.put(xz, hy, "TZ", C.DIM)
    if "xo" in L:
        cv.put(L["xo"], hy, "UTC Offset", C.DIM)
        cv.put(L["xr"], hy, ref_label, C.DIM)
    if "xs" in L:
        cv.put(L["xs"], hy, "Status", C.DIM)
    if "xw" in L:
        cv.put(L["xw"], hy, "Weather", C.DIM)
    draw_ticks(cv, hy, xb, nb, *time_window(st, now), step24=2 if nb >= 48 else 4)
    if n > vis:
        cv.put(xl + 2, y0, " %d-%d of %d " % (top + 1, top + vis, n), C.DIM)

    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    wstart, wspan = time_window(st, now)
    frac = (now - wstart).total_seconds() / (wspan * 3600)
    nowc = xb + min(nb - 1, max(0, int(frac * nb)))
    cv.put(nowc, y0, "\u25bc", C.WHITE, None, True)
    cv.meta["bars"] = (xb, nb, y0 + 2, y0 + height - 1, wstart, wspan)

    utc_h = now.hour + now.minute / 60
    decl, eot = sun_pos(now)
    insts = [wstart + dt.timedelta(hours=(j + 0.5) * wspan / nb) for j in range(nb)]
    min_alpha = [1.0] * nb
    open_count = [0] * nb
    r_off = ref_offset(st, now)
    for i in range(n):
        ci = rows[i]
        alphas = []
        for j in range(nb):
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
        y = y0 + 2 + (i - top)
        cv.meta["rows"][y] = i
        loc, off, abbr = infos[i]
        is_sel = i == sel
        rbg = C.SEL_BG if is_sel else None
        if is_sel:
            cv.fill(xl + 1, y, xb - 2 - xl, C.SEL_BG)
            cv.put(2, y, "▸", ci.color, rbg, True)
        cv.put(xn, y, str(i + 1), C.DIM, rbg)
        cv.put(xc, y, "●", ci.color, rbg)
        nm = ci.name[:15]
        cv.put(xc + 2, y, nm, ci.color, rbg, is_sel)
        is_home = (not mk) and st.home and st.home["zone"] == ci.zone and st.home["name"] == ci.name
        if is_home and len(nm) < 15:
            cv.put(xc + 3 + len(nm), y, "⌂", C.AMBER, rbg, True)
        txt = fmt_local(loc, st.h12)
        other_day = loc.date() != now.date()
        cv.put(xt, y, txt[:3], C.AMBER if other_day else C.DIM, rbg)
        cv.put(xt + 3, y, txt[3:], C.WHITE, rbg, True)
        day = daylight(ci.lat, ci.lon, utc_h, decl, eot) > 0.5
        cv.put(xg, y, "☼" if day else "☾", C.SUN if day else C.MOON, rbg)
        cv.put(xz, y, abbr[:4], ci.color, rbg)
        flag = None
        if not mk:
            g = dst_gap_change(ci, st, now)
            if g and (g[0] - now).days <= 30:
                flag = g
        if flag is not None:
            cv.put(xz + 5, y, "↻", C.AMBER, rbg, True)
        if "xo" in L:
            cv.put(L["xo"], y, fmt_off(off), C.TEXT, rbg)
            if is_home:
                cv.put(L["xr"], y, "home", C.AMBER, rbg)
            else:
                d = off - r_off
                cv.put(L["xr"], y, fmt_rel(d), C.DIM if d.total_seconds() == 0 else C.TEXT, rbg)
        if "xs" in L:
            stxt, scol = status_text(ci, now, st.work)
            cv.put(L["xs"], y, stxt, scol, rbg)
        if "xw" in L:
            wt, wc = weather_cell(ci, st.weather)
            cv.put(L["xw"], y, wt[:12], wc, rbg)
        for j in range(nb):
            a = alphas[j] * (0.5 if st.focus and not is_sel else 1.0)
            col = mix(C.BAR_BG, ci.color, a)
            if xb + j == nowc:
                cv.put(xb + j, y, "┆", C.WHITE, col, True)
            else:
                cv.put(xb + j, y, " ", None, col)
    ly = y0 + 2 + vis
    if ov:
        oc = C.GREEN
        cv.put(xc, ly, "▍", oc)
        if mk:
            cv.put(xc + 2, ly, "Open", oc, None, True)
            now_open = sum(1 for i in range(n) if status_info(rows[i], now, st.work)[0])
            cv.put(xt, ly, "%d of %d open now" % (now_open, n), oc)
        else:
            win = overlap_window(rows, day0, ws, we)
            cv.put(xc + 2, ly, "Overlap", oc, None, True)
            if win is None:
                cv.put(xt, ly, "no common hours", C.DIM)
            else:
                s, e = win
                cv.put(xt, ly, "%02d:%02d–%02d:%02d UTC" % (s // 60, s % 60, (e // 60) % 24, e % 60), oc)
        for j in range(nb):
            if mk:
                a = open_count[j] / n
            else:
                a = min_alpha[j] if min_alpha[j] >= 0.99 else min_alpha[j] * 0.35
            col = mix(C.BAR_BG, oc, a)
            if xb + j == nowc:
                cv.put(xb + j, ly, "┆", C.WHITE, col, True)
            else:
                cv.put(xb + j, ly, " ", None, col)
        ly += 1
    cv.put(nowc, ly, "▲", C.WHITE, None, True)
    label = "UTC " + now.strftime("%H:%M")
    lx = nowc + 2 if nowc + 2 + len(label) < xr else nowc - 2 - len(label)
    if wspan < 24:
        hint = "%gh window \u00b7 [ ] zoom \u00b7 0 reset" % wspan
        if xb + len(hint) + 1 < lx - 1:
            cv.put(xb, ly, hint, C.DIM)
        elif xb + 10 < lx - 1:
            cv.put(xb, ly, "%gh" % wspan, C.DIM)
    cv.put(lx, ly, "UTC", C.DIM)
    cv.put(lx + 4, ly, now.strftime("%H:%M"), C.WHITE, None, True)


def draw_details(cv, W, y, st, infos, rows, sel, now):
    ci = rows[sel]
    loc, off, abbr = infos[sel]
    groups = [[("▸ ", ci.color), (ci.name, ci.color, True), ("  " + ci.zone, C.DIM)]]
    stxt, scol = status_text(ci, now, st.work)
    groups.append([(stxt, scol)])
    if st.weather != "off":
        wt, wc = weather_cell(ci, st.weather, True)
        groups.append([(wt, wc)])
    s = sun_times(ci, now)
    sun = None
    if isinstance(s, str):
        groups.append([("☼ " + s, C.SUN)])
    else:
        r, ss = s
        sun = [("☼ ", C.SUN), (fmt_clock(r, st.h12), C.TEXT), ("  ☾ ", C.MOON), (fmt_clock(ss, st.h12), C.TEXT),
               ("  day %dh%02dm" % divmod(int((ss - r).total_seconds() // 60), 60), C.DIM)]
        groups.append(sun)
    d = (off - ref_offset(st, now)).total_seconds()
    ref = "home" if st.home else "here"
    groups.append([("same as " + ref if d == 0 else "%s from %s" % (fmt_rel(off - ref_offset(st, now)), ref), C.DIM)])
    if not st.markets:
        g = dst_gap_change(ci, st, now)
        tr = next_transition(ci.tz, now)
        if tr:
            days = (tr[0] - now).days
            when = tr[0].astimezone(ci.tz).strftime("%a %d %b")
            sign = "+" if tr[2] > tr[1] else "-"
            delta = abs((tr[2] - tr[1]).total_seconds()) / 3600
            groups.append([("clocks %s%gh %s (%dd)" % (sign, delta, when, days), C.AMBER if days <= 30 else C.DIM)])
        elif loc.dst():
            groups.append([("DST", C.AMBER)])
        if g and (not tr or g[0] != tr[0]):
            groups.append([("gap to %s: %s → %s on %s" % (ref, fmt_rel(g[1]), fmt_rel(g[2]),
                                                               g[0].astimezone(st.home_tz() or ci.tz).strftime("%d %b")), C.AMBER)])
    groups.append([("%.1f°%s %.1f°%s" % (abs(ci.lat), "N" if ci.lat >= 0 else "S",
                                                  abs(ci.lon), "E" if ci.lon >= 0 else "W"), C.DIM)])
    def width(gs):
        return sum(len(seg[0]) for g in gs for seg in g) + 5 * (len(gs) - 1)
    while len(groups) > 3 and width(groups) > W - 4:
        groups.pop()               # least important last: coordinates, gap, clock change, sun ...
    if width(groups) > W - 4 and groups[-1] is sun:
        sun.pop()                  # the day length goes before the sunrise and sunset times do
    while len(groups) > 1 and width(groups) > W - 4:
        groups.pop()
    if width(groups) > W - 4:
        groups[0].pop()            # only the name is left: drop its zone
    x = 2
    for gi, grp in enumerate(groups):
        if gi:
            cv.put(x, y, "  \u00b7  ", C.BORDER)
            x += 5
        for seg in grp:
            if x + len(seg[0]) > W - 1:
                cv.put(x, y, seg[0][:max(0, W - 2 - x)] + "\u2026", seg[1], None, len(seg) > 2 and seg[2])
                return
            cv.put(x, y, seg[0], seg[1], None, len(seg) > 2 and seg[2])
            x += len(seg[0])


def draw_footer(cv, W, y, st):
    if st.markets:
        items = [("←→", "time"), ("↑↓", "select"), ("M", "back to cities"), ("g", "go to"),
                 ("Enter", "focus"), ("T", "theme"), ("?", "help"), ("q", "quit")]
    else:
        items = [("←→", "time"), ("↑↓", "select"), ("a", "add"), ("d", "remove"), ("g", "go to"),
                 ("*", "home"), ("M", "markets"), ("D", "DST"), ("A", "alerts"), ("W", "weather"), ("+-", "zoom"), ("T", "theme"),
                 ("?", "help"), ("q", "quit")]
    x = 2
    for k, d in items:
        if x + len(k) + len(d) + 3 > W - 2:
            break
        cv.put(x, y, k, C.KEY, None, True)
        cv.put(x + len(k) + 1, y, d, C.DIM)
        x += len(k) + len(d) + 3
    text, col, until = st.msg
    if text and time.time() < until:
        t = " %s " % text
        cv.put(max(0, W - len(t) - 1), y, t, col or C.TEXT, C.SEL_BG, True)
