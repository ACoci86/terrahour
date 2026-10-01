"""Online city lookup through the Open-Meteo geocoding API.

Only used while typing in the "add city" box, and only when the built-in list has no answer.
Runs in a background thread.  Set ``TERRAHOUR_OFFLINE=1`` to disable all network access.
"""
import json
import os
import threading
import time
import urllib.parse
import urllib.request


def offline():
    """True when the user asked for no network access at all."""
    return os.environ.get("TERRAHOUR_OFFLINE", "") not in ("", "0")


def _ascii(s):
    import unicodedata
    out = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().strip()
    return out or s


GEO_CACHE = {}          # query -> ("ok", [results]) | ("err", message)
_geo_pending = set()
_geo_query = [""]       # what the user is typing right now


def _geo_fetch(q):
    time.sleep(0.35)                    # wait for the typing to settle
    if _geo_query[0] != q:
        _geo_pending.discard(q)
        return
    try:
        url = ("https://geocoding-api.open-meteo.com/v1/search?name=%s&count=10&language=en&format=json"
               % urllib.parse.quote(q))
        req = urllib.request.Request(url, headers={"User-Agent": "terrahour"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.load(r)
        res = []
        for r in data.get("results") or []:
            tz = r.get("timezone")
            if not tz:
                continue
            ctry = r.get("country", "")
            if r.get("admin1") and r.get("admin1") != r.get("name"):
                ctry = (ctry + ", " + r["admin1"]) if ctry else r["admin1"]
            res.append({"name": _ascii(r["name"]), "zone": tz, "lat": float(r["latitude"]), "lon": float(r["longitude"]),
                        "country": ctry, "pop": int(r.get("population") or 0), "online": True})
        GEO_CACHE[q] = ("ok", res)
    except Exception as e:
        GEO_CACHE[q] = ("err", (str(getattr(e, "reason", e)) or type(e).__name__)[:40])
    finally:
        _geo_pending.discard(q)


def ensure_geo(q):
    q = q.strip().lower()
    _geo_query[0] = q
    if offline():
        return
    if len(q) >= 3 and q not in GEO_CACHE and q not in _geo_pending:
        _geo_pending.add(q)
        threading.Thread(target=_geo_fetch, args=(q,), daemon=True).start()


def geo_status(q):
    q = q.strip().lower()
    if len(q) < 3 or offline():
        return ""
    rec = GEO_CACHE.get(q)
    if rec is None:
        return "searching online..."
    if rec[0] == "err":
        return "online search unavailable (%s)" % rec[1]
    return "online: %d found" % len(rec[1])
