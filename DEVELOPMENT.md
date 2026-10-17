# Working on terrahour

If you want to change the code, this is the page for you. If you just want to use the app,
the [README](README.md) and the [manual](MANUAL.md) are what you need.

## Getting it running from the source

```sh
git clone https://github.com/ACoci86/terrahour
cd terrahour
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

That's it. The app itself needs nothing beyond Python; the only extras are `pytest` for the
tests and `pillow` for the screenshots. (On Windows, pip also brings in the small `tzdata`
package, because Windows has no time zone database of its own. That is the one line under
`dependencies` in `pyproject.toml`.) After this, `.venv/bin/terrahour` runs whatever is
in your working copy, so you can edit a file and start it again straight away.

## Tests

`pytest` takes a few seconds. The tests don't open a terminal and don't touch the network:
they draw frames in memory and press keys through the same code the real app uses, so they
run anywhere. GitHub runs them on Linux (Python 3.9, 3.11 and 3.13) and on macOS for every
push and every pull request.

Three things I use all the time while working on the layout:

```sh
terrahour --once --size 80x24 --at 2026-03-18T14:30Z     # print one frame at any size and time, then exit
TERRAHOUR_OFFLINE=1 terrahour ...                         # never go online
XDG_CONFIG_HOME=/tmp/somewhere terrahour ...              # use a throwaway config instead of your own
```

## Screenshots

The pictures in `docs/` are not real screenshots. `tools/screenshots.py` draws the frames and
paints them with Pillow, so they come out the same on every machine. Run it after a change
that alters how things look, and commit what it produces. It wants the DejaVu fonts; if yours
are somewhere unusual, point `TERRAHOUR_FONT_DIR` at them.

## Where things are

| File | What's in it |
| --- | --- |
| `cli.py` | the command line: options, and the modes that print something and exit |
| `app.py` | the terminal loop: raw mode, reading keys, redrawing only the lines that changed |
| `keys.py` | what every key and mouse event does |
| `compose.py` | decides the layout for the window size and draws a whole frame |
| `draw.py` | the map, the table, the details line, the footer |
| `overlays.py` | the boxes that pop up: add city, go to time, help, radar, alerts |
| `ambient.py` | the big-clock view |
| `canvas.py` | a grid of coloured characters that turns into terminal escape codes |
| `clock.py` | time zones, offsets, open or closed, clock changes, the overlap |
| `astro.py` | where the sun is, sunrise and sunset |
| `worldmap.py` | the land mask, the braille rendering, zoom and pan |
| `places.py`, `geocode.py` | the city database, searching it, and the online lookup |
| `state.py` | everything the app remembers, and the config file |
| `alerts.py`, `weather.py` | what the names say |
| `themes.py` | the colours; everything reads them through `C`, the active theme |
| `data/` | the city list, the land mask and the exchange list, with [their own README](terrahour/data/README.md) |

Two things that are not obvious from the code:

* The map is a grid of 0.25 degree cells saying how much of each cell is land, stored as a
  summed-area table. That lets any zoom level ask "how much land is in this box?" in one
  step, and the braille dots come straight out of the answer.
* The sun's position uses the usual NOAA approximation. It's good to a few minutes, which is
  plenty for a shaded map.

Adding a theme is a new dictionary in `themes.py` and its name in `THEME_ORDER`; nothing
else needs to know.

## Making a release

1. Change `__version__` in `terrahour/__init__.py` and commit.
2. On GitHub, create a release with a tag like `v1.0.7`. That sets off two workflows:
   `publish.yml` sends the package to PyPI, and `binaries.yml` builds a single-file
   executable on Linux (x86_64, ARM64) and macOS (Apple Silicon, Intel) and attaches them
   to the release.
3. If you want to check the executables build without releasing anything, run
   `binaries.yml` by hand from the Actions tab.

PyPI never accepts the same version number twice, and its project page shows the README as
it was when you released, so get the README right before you tag.

## Odds and ends

* The `assets` branch only holds pictures linked from issues. It's not part of the app;
  don't merge it into `main`.
* `tools/binary_entry.py` exists because PyInstaller wants a plain script to start from,
  not a package.
