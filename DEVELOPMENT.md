# Working on terrahour

Notes for anyone changing the code, me included. Users don't need any of this; the
[README](README.md) is for them.

## Set up

```sh
git clone https://github.com/ACoci86/terrahour
cd terrahour
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The app has no third-party dependencies; the dev extras are only `pytest` and `pillow`.
`.venv/bin/terrahour` runs your working copy.

## Tests

`pytest` runs in a few seconds and needs neither a terminal nor the network: the tests
compose frames in memory and drive the app through the same key handler the terminal loop
uses. Every push to `main` and every pull request runs them on Linux (Python 3.9, 3.11, 3.13)
and macOS through GitHub Actions.

Handy while working on the layout:

```sh
terrahour --once --size 80x24 --at 2026-03-18T14:30Z     # one frame, any size, fixed time
TERRAHOUR_OFFLINE=1 ...                                   # never touch the network
XDG_CONFIG_HOME=/tmp/somewhere ...                        # leave your own config alone
```

## Screenshots

`tools/screenshots.py` regenerates everything in `docs/` (the README images and the demo
GIF). It paints frames with Pillow, so the images are reproducible and don't depend on
anyone's terminal. It needs the DejaVu fonts; set `TERRAHOUR_FONT_DIR` if yours live
somewhere unusual.

## How it is put together

| Module | What it does |
| --- | --- |
| `cli.py` | argument parsing and the non-interactive modes |
| `app.py` | the terminal loop: raw mode, input tokens, redraw only the lines that changed |
| `keys.py` | every key and mouse event ends up here |
| `compose.py`, `draw.py`, `overlays.py`, `ambient.py` | turn the state into a frame |
| `canvas.py` | a character grid with colours that renders to ANSI escapes |
| `clock.py` | offsets, formatting, open/closed status, DST transitions, overlap |
| `astro.py` | sun position, sunrise and sunset |
| `worldmap.py` | the land mask, braille rasterisation, zoom and pan |
| `places.py`, `geocode.py` | the city database, search, and the online lookup |
| `state.py` | the State object and the config file |
| `alerts.py`, `weather.py` | what the names say |
| `themes.py` | colours; every module reads them through the active theme object `C` |
| `data/` | the city list, the land mask and the exchange list, with [their own README](terrahour/data/README.md) |

The map is a 0.25 degree land mask folded into a summed-area table, so any zoom level can
ask "how much of this box is land?" in constant time, and the braille cells come straight
out of that. Sun position uses the usual NOAA approximation, good to a few minutes.

Themes are plain dictionaries of RGB tuples in `themes.py`; adding one is a new entry
there plus its name in `THEME_ORDER`.

## Releasing

1. Bump `__version__` in `terrahour/__init__.py` and commit.
2. Create a GitHub release with a `vX.Y.Z` tag. That triggers two workflows:
   `publish.yml` uploads the package to PyPI (trusted publishing, no token stored anywhere)
   and `binaries.yml` builds a single-file executable on Linux (x86_64, ARM64) and macOS
   (Apple Silicon, Intel) with PyInstaller and attaches them to the release.
3. `binaries.yml` can also be run by hand from the Actions tab to check the builds without
   publishing anything.

PyPI never accepts the same version twice, so get the README right before tagging: the
project page shows the README as it was at release time.

## Odds and ends

* The `assets` branch holds only images linked from issues. It is not part of the app and
  should not be merged into `main`.
* `tools/binary_entry.py` exists because PyInstaller wants a plain script as the entry
  point, not a package.
