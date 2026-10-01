"""Non-interactive output: one line for a status bar, a live --watch line, and JSON."""
import json
import re
import shutil
import sys
import time

from .clock import fmt_clock, is_open, next_transition, parse_at, status_info, utcnow
from .themes import C, mix


def short_label(name):
    words = re.split(r"[\s/_-]+", name.strip())
    if len(words) > 1:
        return "".join(w[0] for w in words if w).upper()[:4]
    return name[:3].upper()


def line_parts(st, now, seconds=False):
    parts = []
    day = now.date()
    for c in st.cities:
        loc = now.astimezone(c.tz)
        t = loc.strftime("%I:%M:%S %p").lstrip("0") if (st.h12 and seconds) else \
            loc.strftime("%H:%M:%S") if seconds else fmt_clock(loc, st.h12)
        d = (loc.date() - day).days
        txt = "%s %s%s" % (short_label(c.name), t, "%+d" % d if d else "")
        o = is_open(c, loc, st.work)
        parts.append((txt, c.color if o else mix(C.BG, c.color, 0.5)))
    return parts


def render_parts(parts, tmux=False, color=False, extra=""):
    out = []
    for txt, col in parts:
        if tmux:
            txt = "#[fg=#%02x%02x%02x]%s#[default]" % (col + (txt,))
        elif color:
            txt = "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (col + (txt,))
        out.append(txt)
    return " · ".join(out) + extra


def line_output(st, now, tmux, color, seconds=False):
    return render_parts(line_parts(st, now, seconds), tmux, color)


def fit_line(st, now, width, color, seconds=False):
    """As many cities as fit in `width` columns; the rest collapse into '+N'."""
    parts = line_parts(st, now, seconds)
    n = len(parts)
    for k in range(n, 0, -1):
        extra = " +%d" % (n - k) if k < n else ""
        plain = " · ".join(t for t, _ in parts[:k]) + extra
        if len(plain) <= width - 1:
            return render_parts(parts[:k], False, color, extra)
    return parts[0][0][:max(1, width - 1)]


def watch(st, args):
    out = sys.stdout
    tty = out.isatty()
    last = None
    try:
        if tty:
            out.write("\x1b[?25l")
        while True:
            now = utcnow().replace(microsecond=0)
            if args.at:
                now = parse_at(args.at)
            width = shutil.get_terminal_size((100, 24)).columns
            line = fit_line(st, now, width, tty, args.seconds)
            if line != last:
                out.write(("\r" + line + "\x1b[K") if tty else (line + "\n"))
                out.flush()
                last = line
            time.sleep(1.0 - (time.time() % 1.0) + 0.01)
    except KeyboardInterrupt:
        pass
    finally:
        if tty:
            out.write("\x1b[0m\x1b[?25h\n")
            out.flush()


def json_output(st, now):
    out = []
    for c in st.cities:
        loc, off, abbr = c.info(now)
        o, mins = status_info(c, now, st.work)
        tr = next_transition(c.tz, now)
        out.append({"name": c.name, "zone": c.zone, "local_time": loc.isoformat(timespec="minutes"),
                    "utc_offset_minutes": int(off.total_seconds() // 60), "abbreviation": abbr,
                    "open": o, "minutes_to_change": mins,
                    "next_clock_change": tr[0].isoformat(timespec="minutes") if tr else None})
    return json.dumps({"utc": now.isoformat(timespec="seconds"), "cities": out}, indent=2)
