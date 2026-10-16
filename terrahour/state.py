"""Application state and the on-disk config file (~/.config/terrahour/config.json)."""
import json
import math
import os
import tempfile
import time
from zoneinfo import ZoneInfo

from .clock import local_zone
from .places import City, default_cities, make_city, markets
from .themes import C, THEMES, apply_theme


WORK_PRESETS = [(9, 17), (8, 18), (10, 19), (7, 15)]


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "terrahour", "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class State:
    def __init__(self):
        self.cities = []
        self.sel = 0
        self.msel = 0
        self.markets = False
        self.focus = False
        self.h12 = False
        self.frozen = None
        self.work = (9, 17)
        self.overlap = True
        self.home = None            # {"name":..., "zone":...}
        self.weather = "off"        # off | c | f
        self.alerts = []
        self.aidx = 0
        self.mode = None            # None add goto help radar alerts alertnew
        self.help_page = 0          # which page of the key list is open
        self.help_size = None       # (W, H) the help was last drawn for, so keys know how many pages there are
        self.buf = ""
        self.results = []
        self.ridx = 0
        self.err = ""
        self.msg = ("", None, 0.0)
        self.banner = ("", 0.0)
        self.persist = True
        self.mouse = True
        self.compact = "auto"       # auto | on | off
        self.mzi = 0                # map zoom index into ZOOMS
        self.mcenter = None         # (lat, lon) after panning / zooming at the pointer; None = follow the selection
        self.tsi = 0                # time-axis zoom index into TSPANS
        self.wheel = "zoom"         # zoom | scrub
        self.night_shade = 0.0      # shade over the night side of the map, 0 (off) to 1
        self.drag = None
        self.ambient = False        # screensaver view
        self.amb_pin = None         # featured city index; None = cycle automatically
        self.amb_clon = 0.0
        self.amb_drift = False      # slow sideways drift of the map (off by default)
        self.amb_follow = None      # hours since midnight; the ambient map keeps where it is that time in the centre
        self.amb_t0 = 0.0           # when ambient mode was entered (hint shows briefly)

    # rows currently shown and the cursor on them
    def rows(self):
        return markets() if self.markets else self.cities

    def cursor(self):
        return self.msel if self.markets else self.sel

    def set_cursor(self, i):
        self.mcenter = None
        if self.markets:
            self.msel = i
        else:
            self.sel = i

    def home_tz(self):
        if self.home:
            try:
                return ZoneInfo(self.home["zone"])
            except Exception:
                return None
        return local_zone()

    def save(self):
        if not self.persist:
            return
        try:
            p = config_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix=".config")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump({"cities": [c.to_json() for c in self.cities], "h12": self.h12,
                               "work": list(self.work), "overlap": self.overlap, "theme": C.name,
                               "home": self.home, "weather": self.weather, "compact": self.compact,
                               "wheel": self.wheel, "amb_follow": self.amb_follow,
                               "night_shade": self.night_shade,
                               "alerts": [{k: v for k, v in a.items() if not k.startswith("_")}
                                          for a in self.alerts if a["kind"] != "timer"]}, f, indent=1)
                os.chmod(tmp, 0o600)
                os.replace(tmp, p)           # only once the file is closed, so it is complete
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError:
            pass

    def say(self, text, color=None, secs=3.5):
        self.msg = (text, color or C.TEXT, time.time() + secs)


def _coord(v, lo, hi):
    """A config coordinate as a finite float in range, else None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and lo <= f <= hi else None


def state_from_config():
    st = State()
    cfg = load_config()
    th = cfg.get("theme", "midnight")
    apply_theme(th if isinstance(th, str) else "midnight")
    try:
        for i, c in enumerate(cfg.get("cities", [])):
            cidx = c.get("cidx")
            if cidx is None:
                col = tuple(c.get("color", ()))
                base = THEMES["midnight"]["PALETTE"]
                cidx = base.index(col) if col in base else i
            lat, lon = _coord(c.get("lat"), -90.0, 90.0), _coord(c.get("lon"), -180.0, 180.0)
            if lat is None or lon is None:
                fb = make_city({"name": c.get("name", "?"), "zone": c["zone"],
                                "lat": None, "lon": None}, st.cities)
                lat = lat if lat is not None else fb.lat
                lon = lon if lon is not None else fb.lon
            st.cities.append(City(c["name"], c["zone"], lat, lon, cidx))
    except Exception:
        st.cities = []
    if not st.cities:
        st.cities = default_cities()
    st.h12 = bool(cfg.get("h12", False))
    w = cfg.get("work")
    if isinstance(w, list) and len(w) == 2:
        try:
            h1, h2 = int(w[0]), int(w[1])
        except (TypeError, ValueError, OverflowError):
            pass
        else:
            if 0 <= h1 <= 24 and 0 <= h2 <= 24:
                st.work = (h1, h2)
    st.overlap = bool(cfg.get("overlap", True))
    h = cfg.get("home")
    if isinstance(h, dict) and h.get("zone"):
        try:
            ZoneInfo(h["zone"])
            st.home = {"name": h.get("name", h["zone"]), "zone": h["zone"]}
        except Exception:
            st.home = None
    st.compact = cfg.get("compact", "auto") if cfg.get("compact") in ("auto", "on", "off") else "auto"
    st.wheel = cfg.get("wheel", "zoom") if cfg.get("wheel") in ("zoom", "scrub") else "zoom"
    f = cfg.get("amb_follow")
    st.amb_follow = float(f) if isinstance(f, (int, float)) and not isinstance(f, bool) and 0 <= f < 24 else None
    try:
        st.night_shade = max(0.0, min(1.0, float(cfg.get("night_shade", 0.0))))
    except (TypeError, ValueError):
        st.night_shade = 0.0
    st.weather = cfg.get("weather", "off") if cfg.get("weather") in ("off", "c", "f") else "off"
    st.alerts = [a for a in cfg.get("alerts", []) if _alert_ok(a)]
    return st


def _alert_ok(a):
    """A config alert with all the fields its kind needs, else False."""
    if not isinstance(a, dict) or a.get("kind") not in ("time", "open", "close"):
        return False
    if not isinstance(a.get("name"), str) or not isinstance(a.get("zone"), str):
        return False
    if a["kind"] == "time" and (isinstance(a.get("m"), bool)
                                or not isinstance(a.get("m"), int)
                                or not 0 <= a["m"] < 1440):
        return False
    return True
