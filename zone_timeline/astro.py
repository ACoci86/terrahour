"""Just enough astronomy for day/night shading and sunrise/sunset times."""
import datetime as dt
import math


def sun_pos(t):
    n = t.timetuple().tm_yday + (t.hour + t.minute / 60) / 24
    g = 2 * math.pi / 365 * (n - 1)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    return decl, eot


def daylight(lat, lon, utc_h, decl, eot):
    h = math.radians(15 * (utc_h + eot / 60 - 12) + lon)
    la = math.radians(lat)
    elev = math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(h)
    return max(0.0, min(1.0, (elev + 0.08) / 0.16))


def sun_times(city, now):
    """(sunrise, sunset) as aware datetimes in the city's tz, or a string for polar day/night."""
    loc = now.astimezone(city.tz)
    base = dt.datetime(loc.year, loc.month, loc.day, tzinfo=dt.timezone.utc)
    noon_utc = base + dt.timedelta(hours=12 - city.lon / 15)
    decl, eot = sun_pos(noon_utc)
    noon_h = 12 - city.lon / 15 - eot / 60
    la = math.radians(city.lat)
    x = (math.cos(math.radians(90.833)) - math.sin(la) * math.sin(decl)) / (math.cos(la) * math.cos(decl))
    if x >= 1:
        return "polar night"
    if x <= -1:
        return "midnight sun"
    ha = math.degrees(math.acos(x)) / 15
    rise = (base + dt.timedelta(hours=noon_h - ha)).astimezone(city.tz)
    sett = (base + dt.timedelta(hours=noon_h + ha)).astimezone(city.tz)
    return rise, sett
