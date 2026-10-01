"""Shared fixtures.

Every test runs with: no network (TERRAHOUR_OFFLINE), a throwaway config directory, the
system zone pinned to UTC, and the midnight theme active.
"""
import datetime as dt
import time

import pytest

from terrahour import clock
from terrahour.places import default_cities
from terrahour.state import State
from terrahour.themes import apply_theme

# A Wednesday. 14:30 UTC means New York and London are inside working hours, Tokyo is at 23:30.
FIXED = dt.datetime(2026, 3, 18, 14, 30, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TERRAHOUR_OFFLINE", "1")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    monkeypatch.setattr(clock, "_local_zone", "unset")
    apply_theme("midnight")
    yield
    apply_theme("midnight")


@pytest.fixture
def now():
    return FIXED


@pytest.fixture
def state():
    """Default cities, nothing persisted to disk."""
    st = State()
    st.cities = default_cities()
    st.persist = False
    return st
