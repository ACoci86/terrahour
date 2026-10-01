#!/usr/bin/env python3
"""Render the README screenshots and the demo GIF without a terminal.

Frames are composed exactly as the app would draw them, then painted cell by cell with Pillow,
so the images are reproducible and do not depend on anyone's terminal setup.

    pip install pillow
    python tools/screenshots.py            # writes docs/*.png and docs/demo.gif

Fonts: DejaVu Sans Mono for text, DejaVu Sans for braille (the mono face has none) and Symbola
for the one or two symbols neither has. Override with ZT_FONT_DIR if yours live elsewhere.
"""
import datetime as dt
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ZONE_TIMELINE_OFFLINE"] = "1"       # never hit the network while rendering
os.environ["TZ"] = "UTC"
time.tzset()

from zone_timeline.compose import compose            # noqa: E402
from zone_timeline.keys import handle_key            # noqa: E402
from zone_timeline.places import default_cities      # noqa: E402
from zone_timeline.state import State                # noqa: E402
from zone_timeline.themes import C, apply_theme      # noqa: E402

DOCS = ROOT / "docs"
NOW = dt.datetime(2026, 3, 18, 14, 30, tzinfo=dt.timezone.utc)
FONT_DIR = Path(os.environ.get("ZT_FONT_DIR", "/usr/share/fonts/truetype"))
FONTS = {
    "regular": FONT_DIR / "dejavu/DejaVuSansMono.ttf",
    "bold": FONT_DIR / "dejavu/DejaVuSansMono-Bold.ttf",
    "braille": FONT_DIR / "dejavu/DejaVuSans.ttf",
    "symbols": FONT_DIR / "ancient-scripts/Symbola_hint.ttf",
}
SIZE = 15


class Painter:
    def __init__(self, size=SIZE):
        self.f = {k: ImageFont.truetype(str(p), size) for k, p in FONTS.items() if p.exists()}
        if "regular" not in self.f:
            sys.exit("DejaVu Sans Mono not found; set ZT_FONT_DIR")
        self.cw = round(self.f["regular"].getlength("M"))
        self.ch = round(size * 1.25)

    def font_for(self, ch, bold):
        o = ord(ch)
        if 0x2800 <= o <= 0x28FF:
            return self.f.get("braille", self.f["regular"])
        if ch == "⏸":
            return self.f.get("symbols", self.f["regular"])
        return self.f["bold"] if bold and "bold" in self.f else self.f["regular"]

    def paint(self, cv, pad=12):
        W, H = cv.w, cv.h
        img = Image.new("RGB", (W * self.cw + 2 * pad, H * self.ch + 2 * pad), C.BG)
        d = ImageDraw.Draw(img)
        for y in range(H):
            for x in range(W):
                fg, bg, bold = cv.st[y][x]
                px, py = pad + x * self.cw, pad + y * self.ch
                if bg and bg != C.BG:
                    d.rectangle([px, py, px + self.cw - 1, py + self.ch - 1], fill=bg)
                ch = cv.ch[y][x]
                if ch != " ":
                    font = self.font_for(ch, bold)
                    if ch == "█":                       # full block: draw it as a rectangle, it tiles better
                        d.rectangle([px, py, px + self.cw - 1, py + self.ch - 1], fill=fg or C.TEXT)
                        continue
                    d.text((px, py), ch, font=font, fill=fg or C.TEXT)
        return img


class Clock:
    """A fake time.time() so footer messages fade at the right GIF frame instead of in real seconds."""

    def __init__(self):
        self.t = time.time()
        time.time = lambda: self.t

    def advance(self, seconds):
        self.t += seconds


def fresh_state(**kw):
    apply_theme("midnight")
    st = State()
    st.cities = default_cities()
    st.persist = False
    st.home = {"name": "London", "zone": "Europe/London"}
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def frame(st, W, H, now=NOW):
    return compose(W, H, st, st.frozen or now, now)


def png(name, st, W, H, painter):
    painter.paint(frame(st, W, H)).save(DOCS / name, optimize=True)
    print("wrote", name)


def still_images(painter):
    png("main.png", fresh_state(), 120, 38, painter)
    png("markets.png", fresh_state(markets=True), 120, 38, painter)
    png("compact.png", fresh_state(compact="on"), 72, 16, painter)
    st = fresh_state(ambient=True, amb_t0=time.time() - 60, amb_pin=3)
    png("ambient.png", st, 100, 30, painter)
    png("radar.png", fresh_state(mode="radar", sel=2), 120, 38, painter)
    st = fresh_state(mode="add", buf="naples")
    from zone_timeline.places import refresh_results
    refresh_results(st)
    png("add-city.png", st, 120, 38, painter)
    for theme in ("light", "nord"):
        apply_theme(theme)
        st = fresh_state()
        apply_theme(theme)
        png("theme-%s.png" % theme, st, 120, 38, painter)
    apply_theme("midnight")


def demo_gif(painter, clock):
    W, H = 110, 34
    st = fresh_state()
    frames, delays = [], []

    def shot(hold):
        frames.append(painter.paint(frame(st, W, H)).quantize(colors=128, method=Image.Quantize.MEDIANCUT))
        delays.append(int(hold * 1000))
        clock.advance(hold)

    def key(k, hold=0.5):
        handle_key(st, k, NOW, st.frozen or NOW)
        shot(hold)

    shot(2.2)
    for _ in range(6):                                  # scrub an hour and a half into the future
        key("\x1b[C", 0.25)
    shot(1.0)
    key("j", 0.4)
    key("j", 0.6)
    key("\r", 1.6)                                      # focus London
    key("\r", 0.3)
    key("r", 1.0)                                       # back to live
    key("M", 2.2)                                       # exchanges
    key("M", 0.6)
    key("D", 2.6)                                       # DST radar
    key("\x1b", 0.4)
    key("a", 0.6)
    for ch in "naples":
        key(ch, 0.18)
    shot(0.8)
    key("\r", 1.8)                                      # Naples is on the map now
    key("+", 1.2)                                       # zoom the map on the selection
    key("+", 1.6)
    key("0", 0.8)
    key("T", 1.4)                                       # themes
    key("T", 1.4)
    key("T", 1.4)
    key("T", 0.3)
    key("T", 0.3)
    key("T", 0.6)                                       # back to midnight
    key("?", 2.6)                                       # help
    key("\x1b", 0.4)
    key("V", 2.4)                                       # ambient view
    key("V", 1.6)
    frames[0].save(DOCS / "demo.gif", save_all=True, append_images=frames[1:], duration=delays, loop=0,
                   optimize=True)
    print("wrote demo.gif (%d frames, %.1fs)" % (len(frames), sum(delays) / 1000))


def main():
    DOCS.mkdir(exist_ok=True)
    painter = Painter()
    clock = Clock()
    still_images(painter)
    demo_gif(painter, clock)


if __name__ == "__main__":
    main()
