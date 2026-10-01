"""The interactive loop: raw terminal, redraw only the lines that changed, dispatch input."""
import os
import re
import select
import shutil
import sys
import time

from .alerts import check_alerts, notify
from .clock import utcnow
from .compose import compose
from .keys import handle_key, handle_mouse
from .places import refresh_results
from .themes import C


MOUSE_ON = "\x1b[?1002h\x1b[?1006h"
MOUSE_OFF = "\x1b[?1006l\x1b[?1002l"
TOKENS = re.compile(r"\x1b\[<\d+;\d+;\d+[Mm]|\x1b\[[0-9;]*[A-Za-z~]|\x1bO.|\x1b|.", re.S)


def run(st, fixed_at):
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[2J" + (MOUSE_ON if st.mouse else ""))
    out.flush()
    if fixed_at:
        st.frozen = fixed_at
    prev, prev_size, meta = [], None, {}
    try:
        tty.setcbreak(fd)
        while True:
            W, H = shutil.get_terminal_size((100, 30))
            if (W, H) != prev_size:
                out.write("\x1b[2J")
                prev, prev_size = [], (W, H)
            live = utcnow()
            for msg in check_alerts(st, live):
                st.banner = (msg, time.time() + 12)
                st.say(msg, C.AMBER, 12)
                out.write("\a")
                notify(msg)
            if st.mode == "add":
                refresh_results(st)      # pick up online results as they arrive
            now = st.frozen or live.replace(microsecond=0)
            cv = compose(W, H, st, now, live.replace(microsecond=0))
            meta = cv.meta
            lines = cv.lines()
            for y, ln in enumerate(lines):
                if y >= len(prev) or prev[y] != ln:
                    out.write("\x1b[%d;1H%s" % (y + 1, ln))
            out.flush()
            prev = lines
            timeout = 0.2 if st.mode == "add" else 1.05 - live.microsecond / 1e6
            if select.select([fd], [], [], max(0.05, min(timeout, 1.0)))[0]:
                data = os.read(fd, 1024).decode("utf-8", "ignore")
                for k in TOKENS.findall(data):
                    mm = re.fullmatch(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])", k)
                    if mm:
                        handle_mouse(st, meta, int(mm.group(1)), int(mm.group(2)) - 1, int(mm.group(3)) - 1,
                                     mm.group(4) == "M", live, now)
                    elif handle_key(st, k, live, now):
                        return
                    now = st.frozen or live.replace(microsecond=0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[0m" + (MOUSE_OFF if st.mouse else "") + "\x1b[?25h\x1b[?1049l")
        out.flush()
