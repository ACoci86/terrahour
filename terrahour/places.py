"""Cities, time zones and stock exchanges: the searchable place database and the City row type."""
import datetime as dt
import gzip
import os
import re
import sys
from importlib import resources
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .geocode import GEO_CACHE, _ascii
from .themes import C


def _data(name):
    return resources.files(__package__).joinpath("data").joinpath(name)


def read_data(name):
    """Text of a bundled data file (transparently gunzipped when the name ends in .gz)."""
    raw = _data(name).read_bytes()
    if name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return raw.decode("utf-8")


def _rows(text):
    for line in text.splitlines():
        if line and not line.startswith("#"):
            yield line


ABBR = {
    "Asia/Dubai": "GST", "Asia/Singapore": "SGT", "Asia/Hong_Kong": "HKT", "Asia/Bangkok": "ICT",
    "Asia/Jakarta": "WIB", "Asia/Karachi": "PKT", "Asia/Seoul": "KST", "Asia/Manila": "PHT",
    "Asia/Kathmandu": "NPT", "Asia/Tehran": "IRST", "Asia/Riyadh": "AST", "Europe/Moscow": "MSK",
    "Europe/Istanbul": "TRT", "America/Sao_Paulo": "BRT", "America/Argentina/Buenos_Aires": "ART",
    "America/Bogota": "COT", "America/Lima": "PET", "Asia/Dhaka": "BST", "Asia/Tashkent": "UZT",
    "Asia/Ho_Chi_Minh": "ICT", "Asia/Kuala_Lumpur": "MYT", "Asia/Taipei": "CST",
    "Africa/Lagos": "WAT", "Africa/Nairobi": "EAT", "Africa/Casablanca": "WET",
    "Pacific/Fiji": "FJT", "America/Santiago": "CLT", "Asia/Jerusalem": "IST",
}


DEFAULT_NAMES = ["San Francisco", "New York", "London", "UTC", "Dubai", "Mumbai",
                 "Singapore", "Tokyo", "Sydney"]


def _dms(s, deg):
    sign = -1 if s[0] == "-" else 1
    d = s[1:]
    return sign * (int(d[:deg]) + int(d[deg:deg + 2] or 0) / 60 + int(d[deg + 2:deg + 4] or 0) / 3600)


_db = None
def city_db():
    """Searchable places: a curated list, ~6,000 cities over 100k people (GeoNames, CC-BY 4.0), and zone.tab."""
    global _db
    if _db is not None:
        return _db
    db, seen = [], set()
    for line in _rows(read_data("curated.txt")):
        n, z, la, lo = line.split("|")
        db.append({"name": n, "zone": z, "lat": float(la), "lon": float(lo), "hay": n.lower(),
                   "alts": [], "pop": 3_000_000, "country": ""})
        seen.add(z + "|" + n.lower())
    countries = {}
    try:
        for line in read_data("cities.txt.gz").split("\n"):
            if line.startswith("@"):
                cc, name = line[1:].split("|")
                countries[cc] = name
                continue
            f = line.split("|")
            if len(f) < 7:
                continue
            name, cc, la, lo, tz, pop, alts = f[0], f[1], f[2], f[3], f[4], f[5], f[6]
            key = tz + "|" + name.lower()
            if key in seen:
                continue
            seen.add(key)
            al = [a for a in alts.split(";") if a]
            country = countries.get(cc, cc)
            db.append({"name": name, "zone": tz, "lat": float(la), "lon": float(lo),
                       "hay": " ".join([name, country] + al).lower(), "alts": [a.lower() for a in al],
                       "pop": int(pop), "country": country})
    except Exception:
        pass
    zone_cc = {}
    for p in ("/usr/share/zoneinfo/iso3166.tab", "/usr/share/lib/zoneinfo/tab/iso3166.tab"):
        if os.path.exists(p):
            for line in open(p, encoding="utf-8", errors="ignore"):
                f = line.rstrip("\n").split("\t")
                if len(f) == 2 and not line.startswith("#"):
                    countries.setdefault(f[0], f[1])
            break
    for p in ("/usr/share/zoneinfo/zone.tab", "/usr/share/lib/zoneinfo/tab/zone.tab"):
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 3:
                continue
            m = re.match(r"([+-]\d+)([+-]\d+)$", f[1])
            if not m:
                continue
            zone = f[2]
            name = zone.split("/")[-1].replace("_", " ")
            cc = countries.get(f[0], f[0])
            zone_cc[zone] = cc
            if zone + "|" + name.lower() in seen:
                continue
            seen.add(zone + "|" + name.lower())
            hay = " ".join((name, zone, cc, f[3] if len(f) > 3 else "")).lower()
            db.append({"name": name, "zone": zone, "lat": _dms(m.group(1), 2), "lon": _dms(m.group(2), 3),
                       "hay": hay, "alts": [], "pop": 0, "country": cc})
        break
    for e in db:
        if not e["country"]:
            e["country"] = zone_cc.get(e["zone"], "")
            if e["country"] and e["country"].lower() not in e["hay"]:
                e["hay"] += " " + e["country"].lower()
    _db = db
    return db


def search_db(q, limit=8, online=False):
    toks = _ascii(q).lower().split()
    if not toks:
        return []
    res = []
    for e in city_db():
        zl = e["zone"].lower()
        if all(t in e["hay"] or ((len(toks) > 1 or "/" in t) and t in zl) for t in toks):
            nm = e["name"].lower()
            words = nm.split()
            if nm == _ascii(" ".join(toks)).lower():
                sc = -2
            elif "/" in toks[0] and zl.endswith("/" + nm.replace(" ", "_")):
                sc = -1
            elif nm.startswith(toks[0]):
                sc = 0
            elif any(w.startswith(toks[0]) for w in words) or any(a.startswith(toks[0]) for a in e["alts"]):
                sc = 1
            elif toks[0] in nm:
                sc = 2
            else:
                sc = 3
            res.append((sc, -e["pop"], len(nm), e))
    res.sort(key=lambda r: r[:3])
    out = [r[3] for r in res[:limit]]
    zone_guess = q.strip().replace(" ", "_")
    if "/" in zone_guess and not any(e["zone"].lower() == zone_guess.lower() for e in out):
        try:
            ZoneInfo(zone_guess)
            out.insert(0, {"name": zone_guess.split("/")[-1].replace("_", " "), "zone": zone_guess,
                           "lat": None, "lon": None, "country": "", "pop": 0})
        except Exception:
            pass
    if online:
        rec = GEO_CACHE.get(q.strip().lower())
        if rec and rec[0] == "ok":
            for o in rec[1]:
                if len(out) >= limit:
                    break
                if any(e["name"].lower() == o["name"].lower() and e["zone"] == o["zone"]
                       and e.get("lat") is not None and abs(e["lat"] - o["lat"]) < 0.6 for e in out):
                    continue
                try:
                    ZoneInfo(o["zone"])
                except Exception:
                    continue
                out.append(o)
    return out[:limit]


def refresh_results(st):
    """Recompute add-city results: offline matches plus whatever the online lookup has returned so far."""
    keep = None
    if st.results and 0 <= st.ridx < len(st.results):
        keep = (st.results[st.ridx]["name"], st.results[st.ridx]["zone"])
    st.results = search_db(st.buf, 8, online=True)
    st.ridx = 0
    if keep:
        for i, e in enumerate(st.results):
            if (e["name"], e["zone"]) == keep:
                st.ridx = i
                break


class City:
    """A row in the table: a city (working hours) or an exchange (explicit sessions)."""

    def __init__(self, name, zone, lat, lon, cidx, sessions=None, weekdays=False):
        self.name, self.zone, self.lat, self.lon, self.cidx = name, zone, lat, lon, int(cidx)
        self.sessions = tuple(sessions) if sessions else None
        self.weekdays = weekdays
        self.tz = ZoneInfo(zone)

    @property
    def color(self):
        return C.PALETTE[self.cidx % len(C.PALETTE)]

    def info(self, now):
        loc = now.astimezone(self.tz)
        off = loc.utcoffset()
        abbr = loc.tzname() or ""
        if not abbr or abbr[0] in "+-" or abbr.startswith("GMT"):
            abbr = ABBR.get(self.zone, "UTC" if self.zone == "UTC" else abbr)
        return loc, off, abbr

    def to_json(self):
        return {"name": self.name, "zone": self.zone, "lat": self.lat, "lon": self.lon, "cidx": self.cidx}


def parse_sessions(spec):
    out = []
    for part in spec.split(","):
        a, b = part.split("-")
        h1, m1 = a.split(":")
        h2, m2 = b.split(":")
        out.append((int(h1) * 60 + int(m1), int(h2) * 60 + int(m2)))
    return out


_markets = None
def markets():
    global _markets
    if _markets is None:
        _markets = []
        for i, line in enumerate(_rows(read_data("markets.txt"))):
            n, z, la, lo, sess = line.split("|")
            _markets.append(City(n, z, float(la), float(lo), i, parse_sessions(sess), True))
    return _markets


def next_cidx(cities):
    used = {c.cidx % len(C.PALETTE) for c in cities}
    for i in range(len(C.PALETTE)):
        if i not in used:
            return i
    return len(cities) % len(C.PALETTE)


def make_city(entry, cities):
    lat, lon = entry.get("lat"), entry.get("lon")
    tz = ZoneInfo(entry["zone"])
    if lat is None:
        look = next((e for e in city_db() if e["zone"] == entry["zone"]), None)
        if look:
            lat, lon = look["lat"], look["lon"]
        else:
            off = dt.datetime.now(dt.timezone.utc).astimezone(tz).utcoffset().total_seconds() / 3600
            lat, lon = 20.0, off * 15
    return City(_ascii(entry["name"]), entry["zone"], lat, lon, next_cidx(cities))


def default_cities():
    by = {}
    for e in city_db():
        by.setdefault(e["name"], e)         # first match = the curated entry (there is also a London, Ontario)
    return [City(by[n]["name"], by[n]["zone"], by[n]["lat"], by[n]["lon"], i) for i, n in enumerate(DEFAULT_NAMES)]


def cities_from_args(specs):
    out = []
    for spec in specs:
        label, _, zone = spec.partition("=") if "=" in spec else ("", "", spec)
        zone = zone.strip()
        try:
            ZoneInfo(zone)
            ent = {"name": label.strip() or zone.split("/")[-1].replace("_", " "), "zone": zone, "lat": None, "lon": None}
        except (ZoneInfoNotFoundError, ValueError):
            found = search_db(zone, 1)          # a city name such as "Naples"
            if not found:
                sys.exit("terrahour: unknown place or time zone %r (try e.g. Naples or Europe/Berlin)" % zone)
            ent = dict(found[0])
            if label.strip():
                ent["name"] = label.strip()
        out.append(make_city(ent, out))
    return out
