"""Alerts: parse what the user typed, check them every second, and notify the desktop."""
import re
import shutil
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from .clock import fmt_clock, is_open
from .places import City, markets, search_db


def resolve_place(st, name):
    """Find a city/exchange by name: current rows, exchanges, then the database. -> (name, zone, market) or None."""
    q = name.strip().lower()
    if not q:
        c = st.rows()[st.cursor()]
        return c.name, c.zone, c.sessions is not None
    for c in st.cities:
        if q in c.name.lower():
            return c.name, c.zone, False
    for c in markets():
        if q in c.name.lower():
            return c.name, c.zone, True
    res = search_db(name, 1)
    if res:
        return res[0]["name"], res[0]["zone"], False
    return None


def parse_alert(text, st):
    """-> (alert dict | None, error)."""
    s = text.strip()
    low = s.lower()
    m = re.fullmatch(r"in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m?)?", low)
    if m and (m.group(1) or m.group(2)):
        secs = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60
        if secs <= 0:
            return None, "Timer must be longer than zero."
        return {"kind": "timer", "name": "timer", "at": time.time() + secs}, ""
    m = re.fullmatch(r"(open|close)\s+(.+)", low)
    if m:
        p = resolve_place(st, m.group(2))
        if not p:
            return None, "Couldn't find %r." % m.group(2)
        return {"kind": m.group(1), "name": p[0], "zone": p[1], "market": p[2]}, ""
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(.*)", low)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if m.group(3):
            if not 1 <= hh <= 12:
                return None, "Hour must be 1-12 with am/pm."
            hh = hh % 12 + (12 if m.group(3) == "pm" else 0)
        if hh > 23 or mm > 59:
            return None, "That isn't a valid time."
        p = resolve_place(st, m.group(4))
        if not p:
            return None, "Couldn't find %r." % m.group(4)
        return {"kind": "time", "name": p[0], "zone": p[1], "m": hh * 60 + mm}, ""
    return None, "Try: 9am tokyo, open new york, close NYSE, in 25m"


def alert_city(a):
    if a.get("market"):
        for c in markets():
            if c.name == a["name"]:
                return c
    return City(a["name"], a["zone"], 0, 0, 0)


def notify(text):
    try:
        if sys.platform == "darwin" and shutil.which("osascript"):
            subprocess.Popen(["osascript", "-e", 'display notification "%s" with title "zone-timeline"' % text.replace('"', "'")],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "zone-timeline", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def check_alerts(st, live):
    """Returns messages for alerts that fired now. Uses real time, not scrubbed time."""
    fired, keep = [], []
    for a in st.alerts:
        try:
            if a["kind"] == "timer":
                if time.time() >= a["at"]:
                    fired.append("Timer finished")
                    continue
            elif a["kind"] == "time":
                loc = live.astimezone(ZoneInfo(a["zone"]))
                today = loc.date().isoformat()
                if loc.hour * 60 + loc.minute == a["m"] and a.get("_last") != today:
                    a["_last"] = today
                    fired.append("%s in %s" % (fmt_clock(loc, st.h12), a["name"]))
            else:
                c = alert_city(a)
                now_open = is_open(c, live.astimezone(c.tz), st.work)
                prev = a.get("_state")
                a["_state"] = now_open
                if prev is not None and prev != now_open and now_open == (a["kind"] == "open"):
                    fired.append("%s %s" % (a["name"], "is open" if now_open else "has closed"))
        except Exception:
            pass
        keep.append(a)
    if len(keep) != len(st.alerts):
        st.alerts = keep
        st.aidx = min(st.aidx, max(0, len(keep) - 1))
    return fired
