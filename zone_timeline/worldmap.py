"""The world map: a land mask rasterised into braille cells, plus zoom and pan maths.

Land coverage at 0.25 degrees (0..15 per cell) comes from Natural Earth 50m, stored in
``data/land_mask.bin.gz``.  It is folded lazily into a summed-area table so any zoom level can ask
"how much of this box is land?" in constant time.
"""
import gzip
import math
from importlib import resources

MASK_W, MASK_H = 1440, 720        # 0.25 degree per cell, whole globe
LAT_TOP, LAT_SPAN = 82.0, 140.0    # map covers lat 82N .. 58S


def load_mask():
    """The raw land mask: MASK_W * MASK_H bytes, row-major from the north, each 0 (sea) to 15 (land)."""
    raw = gzip.decompress(resources.files(__package__).joinpath("data").joinpath("land_mask.bin.gz").read_bytes())
    assert len(raw) == MASK_W * MASK_H
    return raw


_ii = None
_land_cache = {}
_BRAILLE = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
ZOOMS = [1, 2, 3, 4, 6, 8, 12]


def integral():
    global _ii
    if _ii is None:
        from array import array
        from itertools import accumulate
        import operator
        raw = load_mask()
        prev = array("I", [0]) * (MASK_W + 1)
        ii = [prev]
        for r in range(MASK_H):
            cs = [0]
            cs.extend(accumulate(raw[r * MASK_W:(r + 1) * MASK_W]))
            prev = array("I", map(operator.add, cs, prev))
            ii.append(prev)
        _ii = ii
    return _ii


def land_cells(mw, mh, clon, lonspan, ltop, lspan):
    """Braille cells (2x4 dots each) for a map view: grid[r][c] = bitmask 0..255."""
    key = (mw, mh, round(clon, 2), round(lonspan, 2), round(ltop, 2), round(lspan, 2))
    if key in _land_cache:
        return _land_cache[key]
    ii = integral()
    W, H = MASK_W, MASK_H
    dw, dh = mw * 2, mh * 4
    rows_ = []
    for r in range(dh):
        a = (90 - (ltop - r * lspan / dh)) / 180 * H
        b = (90 - (ltop - (r + 1) * lspan / dh)) / 180 * H
        r0 = min(H - 1, max(0, int(a)))
        r1 = min(H, max(r0 + 1, int(math.ceil(b))))
        rows_.append((r0, r1))
    lon0 = clon - lonspan / 2
    cols_ = []
    for c in range(dw):
        a = (lon0 + c * lonspan / dw + 180) / 360 * W
        b = (lon0 + (c + 1) * lonspan / dw + 180) / 360 * W
        c0 = int(math.floor(a))
        wdt = max(1, int(math.ceil(b)) - c0)
        cols_.append((c0 % W, wdt))
    dots = []
    for r0, r1 in rows_:
        top_, bot_ = ii[r0], ii[r1]
        hgt = r1 - r0
        line = []
        for c0, wdt in cols_:
            c1 = c0 + wdt
            if c1 <= W:
                s = bot_[c1] - bot_[c0] - top_[c1] + top_[c0]
            else:
                s = (bot_[W] - bot_[c0] - top_[W] + top_[c0]) + (bot_[c1 - W] - top_[c1 - W])
            line.append(s >= 6 * hgt * wdt)          # 15 = fully land; >= 40% counts as land
        dots.append(line)
    grid = []
    for r in range(mh):
        line = []
        for c in range(mw):
            bits = 0
            for dy in range(4):
                for dx in range(2):
                    if dots[r * 4 + dy][c * 2 + dx]:
                        bits |= _BRAILLE[dy][dx]
            line.append(bits)
        grid.append(line)
    if len(_land_cache) > 24:
        _land_cache.clear()
    _land_cache[key] = grid
    return grid


def map_view(st, rows, sel):
    """(center lon, lon span, top lat, lat span) for the current map zoom."""
    if st.ambient:
        return ((st.amb_clon + 180) % 360) - 180, 360.0, LAT_TOP, LAT_SPAN
    z = ZOOMS[st.mzi]
    if z == 1:
        return 0.0, 360.0, LAT_TOP, LAT_SPAN
    lonspan, lspan = 360 / z, LAT_SPAN / z
    if st.mcenter:
        clat, clon = st.mcenter
    else:
        c = rows[sel]
        clat, clon = c.lat, c.lon
    top = min(88.0, max(-90 + lspan, clat + lspan / 2))
    return ((clon + 180) % 360) - 180, lonspan, top, lspan


def zoom_map(st, rows, delta, anchor=None):
    """Change map zoom. anchor=(fx, fy) keeps the point under the pointer fixed (fractions of the map box)."""
    ni = max(0, min(len(ZOOMS) - 1, st.mzi + delta))
    if ni == st.mzi:
        return False
    sel = min(st.cursor(), len(rows) - 1)
    clon, lonspan, ltop, lspan = map_view(st, rows, sel)
    st.mzi = ni
    if ZOOMS[ni] == 1:
        st.mcenter = None
        return True
    nlon, nspan = 360 / ZOOMS[ni], LAT_SPAN / ZOOMS[ni]
    if anchor:
        fx, fy = anchor
        plon, plat = clon + (fx - 0.5) * lonspan, ltop - fy * lspan
        ntop = plat + fy * nspan
        st.mcenter = (ntop - nspan / 2, plon - (fx - 0.5) * nlon)
    return True
