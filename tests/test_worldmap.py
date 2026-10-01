import pytest

from terrahour.places import City
from terrahour.state import State
from terrahour.worldmap import (LAT_SPAN, LAT_TOP, MASK_H, MASK_W, ZOOMS, integral, land_cells, load_mask,
                                    map_view, zoom_map)


def test_mask_has_the_right_shape_and_a_plausible_amount_of_land():
    raw = load_mask()
    assert len(raw) == MASK_W * MASK_H
    assert max(raw) == 15 and min(raw) == 0
    land = sum(raw) / (15 * len(raw))
    assert 0.25 < land < 0.35          # Earth is about 29% land


def test_integral_table_dimensions():
    ii = integral()
    assert len(ii) == MASK_H + 1 and all(len(r) == MASK_W + 1 for r in ii[:3])
    assert ii[-1][-1] == sum(load_mask())


def test_land_cells_whole_world():
    mw, mh = 100, 20
    grid = land_cells(mw, mh, 0.0, 360.0, LAT_TOP, LAT_SPAN)
    assert len(grid) == mh and all(len(r) == mw for r in grid)
    assert all(0 <= b <= 255 for r in grid for b in r)

    def cell(lat, lon):
        r = int((LAT_TOP - lat) / LAT_SPAN * mh)
        c = int((lon + 180) / 360 * mw)
        return grid[r][c]

    assert cell(50, 30) != 0        # Ukraine
    assert cell(-25, 135) != 0      # Australia
    assert cell(0, -150) == 0       # middle of the Pacific
    assert cell(-40, -20) == 0      # South Atlantic


def test_land_cells_are_cached():
    a = land_cells(60, 12, 0.0, 360.0, LAT_TOP, LAT_SPAN)
    assert land_cells(60, 12, 0.0, 360.0, LAT_TOP, LAT_SPAN) is a


def test_map_view_follows_the_selection_when_zoomed():
    st = State()
    rows = [City("London", "Europe/London", 51.51, -0.13, 0)]
    assert map_view(st, rows, 0) == (0.0, 360.0, LAT_TOP, LAT_SPAN)
    st.mzi = 1                                                   # 2x
    clon, lonspan, top, lspan = map_view(st, rows, 0)
    assert (lonspan, lspan) == (180.0, 70.0)
    assert clon == pytest.approx(rows[0].lon) and top == pytest.approx(86.51)


def test_zoom_map_limits_and_reset():
    st = State()
    rows = [City("London", "Europe/London", 51.51, -0.13, 0)]
    assert not zoom_map(st, rows, -1)                            # already at 1x
    assert zoom_map(st, rows, 1) and ZOOMS[st.mzi] == 2
    for _ in range(10):
        zoom_map(st, rows, 1)
    assert ZOOMS[st.mzi] == ZOOMS[-1] and not zoom_map(st, rows, 1)
    assert zoom_map(st, rows, -len(ZOOMS)) and st.mzi == 0 and st.mcenter is None


def test_zoom_with_an_anchor_keeps_the_point_under_the_pointer():
    st = State()
    rows = [City("London", "Europe/London", 51.51, -0.13, 0)]
    zoom_map(st, rows, 1, anchor=(0.25, 0.5))     # pointer a quarter of the way across: lon -90
    top, clon = st.mcenter
    assert abs((clon - 0.25 * 180 + 90) % 360) < 1e-6
