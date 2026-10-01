"""A grid of characters with per-cell colour that renders to ANSI escape sequences."""
from .themes import C


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ch = [[" "] * w for _ in range(h)]
        self.st = [[(None, C.BG, False)] * w for _ in range(h)]
        self.meta = {"rows": {}, "markers": [], "bars": None, "chip": None, "mode": None}

    def put(self, x, y, text, fg=None, bg=None, bold=False):
        if y < 0 or y >= self.h:
            return
        bg = C.BG if bg is None else bg
        for i, c in enumerate(text):
            xx = x + i
            if 0 <= xx < self.w:
                self.ch[y][xx] = c
                self.st[y][xx] = (fg, bg, bold)

    def fill(self, x, y, w, bg):
        for i in range(w):
            if 0 <= x + i < self.w and 0 <= y < self.h:
                self.st[y][x + i] = (None, bg, False)
                self.ch[y][x + i] = " "

    def lines(self):
        out = []
        for y in range(self.h):
            cur, parts = None, []
            for x in range(self.w):
                st = self.st[y][x]
                if st != cur:
                    parts.append(sgr(st))
                    cur = st
                parts.append(self.ch[y][x])
            parts.append("\x1b[0m")
            out.append("".join(parts))
        return out


def sgr(st):
    fg, bg, bold = st
    s = "\x1b[0"
    if bold:
        s += ";1"
    if fg:
        s += ";38;2;%d;%d;%d" % fg
    if bg:
        s += ";48;2;%d;%d;%d" % bg
    return s + "m"
