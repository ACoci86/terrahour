"""Optional current weather from Open-Meteo (needs network, off by default)."""
import json
import threading
import time
import urllib.request

from .geocode import offline
from .themes import C


WEATHER = {}                    # (lat, lon) -> {"t": temp C, "code": WMO code, "ts": fetched at}
W_STATE = {"err": None, "fails": 0, "next": 0.0, "busy": False}
W_TTL = 900                     # Open-Meteo refreshes "current" every 15 minutes, so asking sooner is pointless
W_MIN_GAP = 60                  # never send two requests less than a minute apart


def _wkey(c):
    return (round(c.lat, 1), round(c.lon, 1))


def _fetch_weather_batch(keys):
    """One request per 20 places (the API takes comma-separated coordinate lists). Never raises."""
    try:
        for i in range(0, len(keys), 20):
            chunk = keys[i:i + 20]
            url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                   "&current=temperature_2m,weather_code&timezone=auto"
                   % (",".join(str(k[0]) for k in chunk), ",".join(str(k[1]) for k in chunk)))
            req = urllib.request.Request(url, headers={"User-Agent": "terrahour"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.load(r)
            items = data if isinstance(data, list) else [data]
            for k, it in zip(chunk, items):
                cur = it["current"]
                WEATHER[k] = {"t": float(cur["temperature_2m"]), "code": int(cur["weather_code"]), "ts": time.time()}
        W_STATE.update(err=None, fails=0, next=time.time() + W_MIN_GAP)
    except Exception as e:
        fails = W_STATE["fails"] + 1
        code = getattr(e, "code", None)
        delay = min(1800, 120 * 2 ** (fails - 1)) if code in (429, 502, 503, 504) else min(600, 30 * 2 ** (fails - 1))
        try:
            delay = max(delay, int(e.headers.get("Retry-After", 0)))      # the server's own request wins
        except Exception:
            pass
        msg = "rate limited" if code == 429 else ("HTTP %d" % code if code else
                                                   (str(getattr(e, "reason", e)) or type(e).__name__)[:30])
        W_STATE.update(err=msg, fails=fails, next=time.time() + delay)     # old values stay on screen
    finally:
        W_STATE["busy"] = False


def weather_refresh(rows):
    """Called every frame; cheap. Starts at most one background request, and only when something is stale."""
    if offline():
        return
    now = time.time()
    if W_STATE["busy"] or now < W_STATE["next"]:
        return
    keys = []
    for c in rows:
        k = _wkey(c)
        rec = WEATHER.get(k)
        if k not in keys and (rec is None or now - rec["ts"] > W_TTL):
            keys.append(k)
    if keys:
        W_STATE["busy"] = True
        threading.Thread(target=_fetch_weather_batch, args=(keys,), daemon=True).start()


def weather_for(c):
    return WEATHER.get(_wkey(c))


def weather_word(code):
    if code == 0:
        return "clear", C.SUN
    if code in (1, 2):
        return "fair" if code == 1 else "partly", C.TEXT
    if code == 3:
        return "cloudy", C.DIM
    if code in (45, 48):
        return "fog", C.DIM
    if code in (51, 53, 55, 56, 57):
        return "drizzle", C.CYAN
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain", C.CYAN
    if code in (71, 73, 75, 77, 85, 86):
        return "snow", C.WHITE
    if code >= 95:
        return "storm", C.AMBER
    return "", C.DIM


def weather_cell(c, units, long=False):
    """(text, colour): the last good value if there is one (even while refreshing or rate-limited), else a status."""
    rec = weather_for(c)
    if rec is not None:
        txt, col = fmt_weather(rec, units)
        if time.time() - rec["ts"] > 3 * W_TTL:
            txt, col = txt + " ?", C.DIM                      # stale: the service has been unreachable for a while
        return txt, col
    if W_STATE["err"]:
        wait = max(1, int((W_STATE["next"] - time.time()) // 60) + 1)
        return (("weather: %s, retrying in %dm" % (W_STATE["err"], wait)) if long else "retry %dm" % wait), C.AMBER
    return "loading...", C.DIM


def fmt_weather(rec, units):
    t = rec["t"] if units == "c" else rec["t"] * 9 / 5 + 32
    word, col = weather_word(rec["code"])
    return "%d°%s %s" % (round(t), units.upper(), word), col
