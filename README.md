# terrahour

![tests](https://github.com/ACoci86/terrahour/actions/workflows/tests.yml/badge.svg)

A world clock for the terminal, with a map that shows where it is daytime and a 24-hour
timeline that shows when your cities are at work. No dependencies, just Python.

![terrahour main view](docs/main.png)

I wrote it because I kept opening a browser tab to work out whether 10am in New York is a
sane time for someone in Singapore. Now I press `g`, type `10am`, and look at the bars.

![demo](docs/demo.gif)

## What it does

* **Map with day and night.** The world is drawn in braille dots, shaded by sunlight, and
  coloured by time zone. Every city you track gets a marker. Zoom with `+` `-` or the mouse
  wheel, drag to pan.
* **A timeline per city.** Each row is a 24-hour bar with the working hours lit up. The
  overlap row at the bottom shows the window when everybody is at their desk.
* **Scrub through time.** Arrow keys move in 15-minute steps, `g` jumps to any time
  ("15:30", "3pm", "+2h", "2026-10-05 09:00"), `r` snaps back to live.
* **DST radar.** `D` lists the next clock change for every city and, more usefully, whether
  the gap between you and them is about to shift by an hour.
* **Stock exchanges.** `M` swaps the city list for the ten biggest exchanges with their real
  trading sessions, lunch breaks included.
* **Alerts.** `A` sets a daily reminder in another city's time, a ping when an office or
  exchange opens or closes, or a plain timer. They ring the bell and send a desktop
  notification while the app is open.
* **Weather**, if you want it. `W` shows the current temperature next to each city
  (Open-Meteo, needs network, off by default).
* **Ambient view.** `V` turns the whole terminal into a big clock over the map that cycles
  through your cities. Nice on a spare monitor.
* **Fits anywhere.** Below about 76 columns it switches to a compact layout that works in a
  tmux split. `--line` prints a one-liner for a status bar.
* **Six themes** (midnight, nord, dracula, light, mono, colorblind), 12 or 24 hour clock,
  mouse support, and about 6,000 cities built in with online lookup for the rest.

| Exchanges | Compact layout for a tmux split |
| --- | --- |
| ![markets view](docs/markets.png) | ![compact view](docs/compact.png) |

| DST radar | Adding a city |
| --- | --- |
| ![DST radar](docs/radar.png) | ![add city](docs/add-city.png) |

| Ambient view | Light theme |
| --- | --- |
| ![ambient view](docs/ambient.png) | ![light theme](docs/theme-light.png) |

## Install

You need Python 3.9 or newer, a terminal with truecolor support (almost all of them these
days) and a UTF-8 locale. Linux and macOS are supported. On Windows use WSL, the app relies on
a Unix terminal.

```sh
pipx install git+https://github.com/ACoci86/terrahour
```

or, without pipx:

```sh
pip install git+https://github.com/ACoci86/terrahour
```

or just clone it and run it in place, there is nothing to build:

```sh
git clone https://github.com/ACoci86/terrahour
cd terrahour
python -m terrahour
```

## Usage

```sh
terrahour                                  # your saved cities (a sensible default set the first time)
terrahour Europe/Berlin "Home=America/Chicago" Naples   # a one-off set of zones or city names, not saved
terrahour --markets                        # start in the exchange view
terrahour --at 2026-10-05T09:00Z           # start frozen at a given time
terrahour --theme nord --12h
terrahour --ambient                        # straight into the screensaver view
terrahour --reset                          # forget saved cities and settings
```

Press `?` inside the app for the full list of keys. The ones you will use most:

| Key | Action |
| --- | --- |
| `←` `→` | scrub 15 minutes (Shift: 1 hour, PgUp/PgDn: 1 day) |
| `g` | go to a time, `r` back to live |
| `↑` `↓` `j` `k` | select a city, Shift moves it up or down the list |
| `a` `d` | add or remove a city |
| `*` | mark the selected city as home (offsets are then relative to it) |
| `Enter` | focus the selected city, dims the others |
| `M` `D` `A` `W` | exchanges, DST radar, alerts, weather |
| `+` `-` `[` `]` `0` | zoom the map, zoom the timeline, reset |
| `T` `t` `c` `V` | theme, 12/24h, compact layout, ambient view |
| `q` | quit |

Everything you change in the app (cities, theme, home, working hours, alerts) is saved to
`~/.config/terrahour/config.json`. Zones given on the command line are session-only and
leave that file alone.

## Status bars and scripts

```sh
$ terrahour --line
SF 07:30 · NY 10:30 · LON 14:30 · UTC 14:30 · DUB 18:30 · MUM 20:00 · SIN 22:30 · TOK 23:30 · SYD 01:30+1

$ terrahour --watch            # the same line, updating in place (good in a small tmux pane)
$ terrahour --tmux             # with tmux colour codes, for your status-right
$ terrahour --json --at 2026-03-18T14:30Z | jq '.cities[] | select(.open)'
```

The JSON includes local time, UTC offset, whether the city is inside working hours, minutes
until that changes, and the next clock change. `--once --size 120x40` prints a single frame of
the full UI, which is how the screenshots above were made.

## Network

Two features talk to the internet, and both are optional:

* While you type in the "add city" box, names that are not in the built-in list are looked up
  through the Open-Meteo geocoding API.
* Weather, when you turn it on with `W`, comes from the Open-Meteo forecast API.

Set `TERRAHOUR_OFFLINE=1` to switch both off. Nothing else leaves your machine.

## How it is put together

It is a single Python package with no third-party dependencies. The pieces:

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

The map is a 0.25 degree land mask folded into a summed-area table, so any zoom level can ask
"how much of this box is land?" in constant time, and the braille cells come straight out of
that. Sun position uses the usual NOAA approximation, good to a few minutes.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The tests do not need a terminal or the network: they compose frames in memory and drive the
app through the same key handler the terminal loop uses. `tools/screenshots.py` regenerates
everything in `docs/` (it needs Pillow and the DejaVu fonts).

## Data and credits

* City list derived from [GeoNames](https://www.geonames.org/) (CC BY 4.0).
* Land mask rasterised from [Natural Earth](https://www.naturalearthdata.com/) (public domain).
* Geocoding and weather from [Open-Meteo](https://open-meteo.com/) (CC BY 4.0).
* Time zone rules come from your operating system's tz database through Python's `zoneinfo`.

## License

MIT. See [LICENSE](LICENSE).
