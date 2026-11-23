#!/usr/bin/env python3
"""Render the README screenshots and the demo GIF without a terminal.

Frames are composed exactly as the app would draw them, then painted cell by cell with Pillow,
so the images are reproducible and do not depend on anyone's terminal setup.

    pip install pillow
    python tools/screenshots.py            # writes docs/*.png and docs/demo.gif
    python tools/screenshots.py --video    # writes the website's demo video into site/img/ (needs ffmpeg)

Fonts: DejaVu Sans Mono for text, DejaVu Sans for braille (the mono face has none) and Symbola
for the one or two symbols neither has. Override with TERRAHOUR_FONT_DIR if yours live elsewhere.
"""
import datetime as dt
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["TERRAHOUR_OFFLINE"] = "1"       # never hit the network while rendering
os.environ["TZ"] = "UTC"
time.tzset()

from terrahour.compose import compose            # noqa: E402
from terrahour.keys import handle_key            # noqa: E402
from terrahour.places import default_cities      # noqa: E402
from terrahour.state import State                # noqa: E402
from terrahour.themes import C, apply_theme      # noqa: E402

DOCS = ROOT / "docs"
NOW = dt.datetime(2026, 3, 18, 14, 30, tzinfo=dt.timezone.utc)
FONT_DIR = Path(os.environ.get("TERRAHOUR_FONT_DIR", "/usr/share/fonts/truetype"))
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
            sys.exit("DejaVu Sans Mono not found; set TERRAHOUR_FONT_DIR")
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
    from terrahour.places import refresh_results
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


def demo_video(painter, clock, fps=25):
    """The website's demo: the same tour as the GIF, but smooth, in full colour, with the clock ticking.

    Frames go straight into ffmpeg as raw pixels, first to a lossless file, then to the WebM and MP4
    the page serves, plus the first frame as the picture shown while the video loads."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found; it is needed for the video")
    out = ROOT / "site" / "img"
    out.mkdir(parents=True, exist_ok=True)
    W, H = 110, 34
    st = fresh_state()
    elapsed = [0.0]
    cache = {}

    def now():
        return NOW + dt.timedelta(seconds=int(elapsed[0]))   # the clock ticks once a second, as in the app

    first = painter.paint(frame(st, W, H, now()))
    first.save(out / "demo-poster.png", optimize=True)
    size = "%dx%d" % first.size
    with tempfile.TemporaryDirectory() as tmp:
        master = Path(tmp) / "master.mkv"
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size, "-r", str(fps),
                                "-i", "-", "-c:v", "libx264rgb", "-crf", "0", "-preset", "ultrafast", str(master)],
                               stdin=subprocess.PIPE)

        def hold(seconds):
            for _ in range(max(1, round(seconds * fps))):
                cv = frame(st, W, H, now())
                k = (tuple(map(tuple, cv.ch)), tuple(map(tuple, cv.st)))
                if k not in cache:
                    cache.clear()
                    cache[k] = painter.paint(cv).tobytes()
                enc.stdin.write(cache[k])
                elapsed[0] += 1 / fps
                clock.advance(1 / fps)

        def key(k, seconds=0.5):
            handle_key(st, k, now(), st.frozen or now())
            hold(seconds)

        hold(2.6)
        for _ in range(8):                                  # scrub two hours into the future
            key("\x1b[C", 0.3)
        hold(1.2)
        key("j", 0.45)
        key("j", 0.7)
        key("\r", 1.8)                                      # focus London
        key("\r", 0.4)
        key("r", 1.2)                                       # back to live
        key("M", 2.6)                                       # exchanges
        key("M", 0.7)
        key("D", 3.0)                                       # DST radar
        key("\x1b", 0.5)
        key("a", 0.7)
        for ch in "naples":
            key(ch, 0.16)
        hold(0.8)
        key("\r", 2.0)                                      # Naples is on the map now
        key("+", 1.3)                                       # zoom the map on the selection
        key("+", 1.8)
        key("0", 0.9)
        for _ in range(4):                                  # a few themes, then back to midnight
            key("T", 1.3)
        key("T", 0.3)
        key("T", 0.7)
        key("?", 2.8)                                       # help
        key("\x1b", 0.5)
        key("V", 3.5)                                       # ambient view
        key("V", 1.5)
        enc.stdin.close()
        if enc.wait():
            sys.exit("ffmpeg failed while recording")
        common = ["ffmpeg", "-v", "error", "-y", "-i", str(master), "-pix_fmt", "yuv420p", "-an"]
        subprocess.run(common + ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "40", "-row-mt", "1", str(out / "demo.webm")], check=True)
        subprocess.run(common + ["-c:v", "libx264", "-preset", "veryslow", "-crf", "26", "-tune", "animation",
                                 "-movflags", "+faststart", str(out / "demo.mp4")], check=True)
    print("wrote site/img/demo.webm, demo.mp4 and demo-poster.png (%.1fs)" % elapsed[0])


def main():
    painter = Painter()
    clock = Clock()
    if "--video" in sys.argv[1:]:
        demo_video(painter, clock)
        return
    DOCS.mkdir(exist_ok=True)
    still_images(painter)
    demo_gif(painter, clock)


if __name__ == "__main__":
    main()
