"""Command line entry point."""
import argparse
import os
import shutil
import sys
import time

from . import __version__
from .app import run
from .clock import parse_at, utcnow
from .compose import compose
from .output import json_output, line_output, watch
from .places import cities_from_args
from .state import config_path, state_from_config
from .themes import THEME_ORDER, apply_theme


def main():
    ap = argparse.ArgumentParser(prog="terrahour", description="World clock, map and 24h planner for the terminal.")
    ap.add_argument("zones", nargs="*", help="IANA zones, optionally Label=Zone (session only; saved cities untouched)")
    ap.add_argument("--at", help="fix the time (ISO 8601, UTC unless it has an offset)")
    ap.add_argument("--once", action="store_true", help="print one frame and exit")
    ap.add_argument("--size", help="WxH for --once (default: terminal size)")
    ap.add_argument("--12h", dest="h12", action="store_true", help="12-hour clock")
    ap.add_argument("--markets", action="store_true", help="start in the stock-exchange view")
    ap.add_argument("--theme", choices=THEME_ORDER, help="colour theme (saved when you change it in the app)")
    ap.add_argument("--no-mouse", action="store_true", help="don't capture the mouse (keeps normal text selection)")
    ap.add_argument("--line", action="store_true", help="print one line, e.g. for a status bar, and exit")
    ap.add_argument("--ambient", action="store_true", help="start in the full-screen ambient (screensaver) view")
    ap.add_argument("--compact", action="store_true", help="small-pane layout without the map")
    ap.add_argument("--watch", action="store_true", help="live one-liner that updates in place (tmux pane, status line)")
    ap.add_argument("--seconds", action="store_true", help="show seconds in --line / --watch")
    ap.add_argument("--tmux", action="store_true", help="like --line with tmux colour codes")
    ap.add_argument("--json", action="store_true", help="print JSON and exit")
    ap.add_argument("--reset", action="store_true", help="forget saved cities and settings")
    ap.add_argument("--version", action="version", version="terrahour " + __version__)
    args = ap.parse_args()
    if args.reset:
        try:
            os.remove(config_path())
            print("terrahour: saved settings removed")
        except FileNotFoundError:
            print("terrahour: nothing to reset")
        return
    st = state_from_config()
    if args.theme:
        apply_theme(args.theme)
    if args.zones:
        st.cities = cities_from_args(args.zones)
        st.persist = False
    if args.h12:
        st.h12 = True
    st.markets = args.markets
    if args.compact:
        st.compact = "on"
    if args.ambient:
        st.ambient = True
        st.amb_t0 = time.time()
    st.mouse = not args.no_mouse
    at = parse_at(args.at) if args.at else None
    if args.watch:
        watch(st, args)
        return
    if args.line or args.tmux or args.json:
        now = at or utcnow().replace(microsecond=0)
        if args.json:
            print(json_output(st, now))
        else:
            print(line_output(st, now, args.tmux, sys.stdout.isatty() and not args.tmux, args.seconds))
        return
    if args.once:
        if args.size:
            W, H = (int(v) for v in args.size.lower().split("x"))
        else:
            W, H = shutil.get_terminal_size((120, 40))
        now = at or utcnow().replace(microsecond=0)
        print("\n".join(compose(W, H, st, now, utcnow().replace(microsecond=0)).lines()))
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("terrahour: needs an interactive terminal (use --once, --line or --json otherwise)")
    try:
        run(st, at)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
