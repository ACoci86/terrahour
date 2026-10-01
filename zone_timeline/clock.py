"""Time maths: offsets, formatting, open/closed status, DST transitions and the timeline window."""
import datetime as dt
import os
import re
from zoneinfo import ZoneInfo

from .themes import C


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def parse_at(s):
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.replace(tzinfo=dt.timezone.utc) if t.tzinfo is None else t.astimezone(dt.timezone.utc)


def parse_goto(text, tz0, now):
    """Return (aware UTC datetime | None for live, error string)."""
    s = text.strip().lower()
    if s in ("", "now", "live"):
        return None, ""
    m = re.fullmatch(r"([+-])\s*(\d+(?:\.\d+)?)\s*([hmd]?)", s)
    if m:
        v = float(m.group(2)) * {"h": 3600, "m": 60, "d": 86400, "": 3600}[m.group(3)]
        return now + dt.timedelta(seconds=v if m.group(1) == "+" else -v), ""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[ t](\d{1,2}):(\d{2})\s*(z|utc)?", s)
    if m:
        y, mo, d, hh, mm = (int(m.group(i)) for i in range(1, 6))
        tz = dt.timezone.utc if m.group(6) else tz0
        try:
            return dt.datetime(y, mo, d, hh, mm, tzinfo=tz).astimezone(dt.timezone.utc), ""
        except ValueError:
            return None, "That date doesn't exist."
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?\s*(am|pm)?\s*(z|utc)?", s)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if m.group(3):
            if not 1 <= hh <= 12:
                return None, "Hour must be 1-12 with am/pm."
            hh = hh % 12 + (12 if m.group(3) == "pm" else 0)
        if hh > 23 or mm > 59:
            return None, "That isn't a valid time."
        tz = dt.timezone.utc if m.group(4) else tz0
        base = now.astimezone(tz)
        try:
            return base.replace(hour=hh, minute=mm, second=0, microsecond=0).astimezone(dt.timezone.utc), ""
        except ValueError:
            return None, "That isn't a valid time."
    return None, "Try 15:30, 3pm, 15:30z, +2h or 2026-10-05 09:00."


_local_zone = "unset"
def local_zone():
    global _local_zone
    if _local_zone != "unset":
        return _local_zone
    z = None
    for getter in (lambda: os.environ.get("TZ", "").lstrip(":"),
                   lambda: os.path.realpath("/etc/localtime").split("zoneinfo/", 1)[1],
                   lambda: open("/etc/timezone").read().strip()):
        try:
            name = getter()
            if name:
                cand = ZoneInfo(name)
                # only trust a zone name if it agrees with what the operating system itself says right now
                if utcnow().astimezone(cand).utcoffset() == dt.datetime.now().astimezone().utcoffset():
                    z = cand
                    break
        except Exception:
            continue
    _local_zone = z
    return z


def ref_offset(st, now):
    tz = st.home_tz()
    return now.astimezone(tz).utcoffset() if tz else now.astimezone().utcoffset()


def fmt_off(td):
    m = int(td.total_seconds() // 60)
    sign = "-" if m < 0 else "+"
    h, mm = divmod(abs(m), 60)
    return "UTC%s%d%s" % (sign, h, ":%02d" % mm if mm else "")


def fmt_rel(td):
    m = int(td.total_seconds() // 60)
    if m == 0:
        return "same"
    h, mm = divmod(abs(m), 60)
    return "%s%d%sh" % ("-" if m < 0 else "+", h, ":%02d" % mm if mm else "")


def fmt_clock(t, h12):
    return t.strftime("%I:%M %p").lstrip("0") if h12 else t.strftime("%H:%M")


def fmt_local(loc, h12):
    return loc.strftime("%a ") + fmt_clock(loc, h12)


def fmt_delta(seconds):
    s = int(round(seconds))
    sign = "-" if s < 0 else "+"
    s = abs(s)
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = ("%dd" % d if d else "") + ("%dh" % h if h else "") + ("%dm" % m if m or not (d or h) else "")
    return sign + parts


def dur(mins):
    if mins >= 1440:
        return "%dd%dh" % (mins // 1440, mins % 1440 // 60)
    if mins >= 60:
        return "%dh%02d" % (mins // 60, mins % 60)
    return "%dm" % mins


def work_alpha(h, ws, we):
    if ws <= h < we:
        return 1.0
    if we <= h < we + 4:
        return 0.55 - 0.43 * (h - we) / 4
    if ws - 2 <= h < ws:
        return 0.12 + 0.43 * (h - (ws - 2)) / 2
    return 0.12


def is_open(c, loc, work):
    if c.weekdays and loc.weekday() >= 5:
        return False
    m = loc.hour * 60 + loc.minute
    if c.sessions:
        return any(a <= m < b for a, b in c.sessions)
    return work[0] * 60 <= m < work[1] * 60


_status_cache = {}
def status_info(c, now, work):
    """(is_open, minutes until the next change or None)."""
    key = (c.zone, c.sessions, c.weekdays, work, int(now.timestamp() // 60))
    if key in _status_cache:
        return _status_cache[key]
    base = now.replace(second=0, microsecond=0)
    s0 = is_open(c, base.astimezone(c.tz), work)
    res = None
    for k in range(1, 8 * 288):          # 5-minute scan over 8 days
        t = base + dt.timedelta(minutes=5 * k)
        if is_open(c, t.astimezone(c.tz), work) != s0:
            for j in range(5 * (k - 1) + 1, 5 * k + 1):
                if is_open(c, (base + dt.timedelta(minutes=j)).astimezone(c.tz), work) != s0:
                    res = j
                    break
            break
    if len(_status_cache) > 600:
        _status_cache.clear()
    _status_cache[key] = (s0, res)
    return s0, res


def status_text(c, now, work):
    o, mins = status_info(c, now, work)
    if mins is None:
        return ("open", C.GREEN) if o else ("closed", C.DIM)
    if o:
        return "open · %s" % dur(mins), (C.AMBER if mins <= 60 else C.GREEN)
    return "opens in %s" % dur(mins), C.DIM


_dst_cache = {}
def next_transition(tz, now):
    """(instant UTC, old offset, new offset) of the next UTC-offset change within ~13 months."""
    key = (getattr(tz, "key", str(tz)), now.date())
    if key in _dst_cache:
        return _dst_cache[key]
    base = now.replace(second=0, microsecond=0)
    off0 = base.astimezone(tz).utcoffset()
    res, prev = None, base
    for i in range(1, 400):
        t = base + dt.timedelta(days=i)
        if t.astimezone(tz).utcoffset() != off0:
            lo, hi = 0, 1440
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if (prev + dt.timedelta(minutes=mid)).astimezone(tz).utcoffset() == off0:
                    lo = mid
                else:
                    hi = mid
            inst = prev + dt.timedelta(minutes=hi)
            res = (inst, off0, inst.astimezone(tz).utcoffset())
            break
        prev = t
    if len(_dst_cache) > 200:
        _dst_cache.clear()
    _dst_cache[key] = res
    return res


def dst_gap_change(c, st, now):
    """If the gap between city and reference changes soon: (instant, old gap, new gap)."""
    ref = st.home_tz()
    trs = [next_transition(c.tz, now)]
    if ref is not None:
        trs.append(next_transition(ref, now))
    trs = [t for t in trs if t]
    if not trs:
        return None
    inst = min(t[0] for t in trs)
    def gap(t):
        co = t.astimezone(c.tz).utcoffset()
        ro = t.astimezone(ref).utcoffset() if ref is not None else t.astimezone().utcoffset()
        return co - ro
    g0, g1 = gap(inst - dt.timedelta(minutes=1)), gap(inst + dt.timedelta(minutes=1))
    return (inst, g0, g1) if g0 != g1 else None


_ov_cache = {}
def overlap_window(rows, day0, ws, we):
    """Longest stretch (UTC minutes of the day) where every row is open."""
    key = (day0.date(), tuple((c.zone, c.sessions, c.weekdays) for c in rows), ws, we)
    if key in _ov_cache:
        return _ov_cache[key]
    flags = []
    for t in range(0, 1440, 5):
        inst = day0 + dt.timedelta(minutes=t)
        flags.append(all(is_open(c, inst.astimezone(c.tz), (ws, we)) for c in rows))
    n = len(flags)
    if all(flags):
        res = (0, 1440)
    elif not any(flags):
        res = None
    else:
        start = next(k for k in range(n) if not flags[k])
        best, k = None, 0
        while k < n:
            if flags[(start + k) % n]:
                j = k
                while j < n and flags[(start + j) % n]:
                    j += 1
                if best is None or (j - k) > best[1] - best[0]:
                    best = (k, j)
                k = j
            else:
                k += 1
        res = (((start + best[0]) % n) * 5, ((start + best[1]) % n) * 5)
    if len(_ov_cache) > 50:
        _ov_cache.clear()
    _ov_cache[key] = res
    return res


TSPANS = [24, 12, 6, 3, 1]


def time_window(st, now):
    """(start, span in hours) of the timeline: the UTC day, or a window centred on the current time."""
    span = TSPANS[st.tsi]
    if span >= 24:
        return now.replace(hour=0, minute=0, second=0, microsecond=0), 24.0
    return now - dt.timedelta(hours=span / 2), float(span)
