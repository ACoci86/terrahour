"""End-to-end: run the command line in a subprocess with an isolated environment."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-03-18T14:30:00Z"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run(*args, env=None):
    e = dict(os.environ, PYTHONPATH=str(ROOT), ZONE_TIMELINE_OFFLINE="1", TZ="UTC")
    e.update(env or {})
    return subprocess.run([sys.executable, "-m", "zone_timeline", *args], capture_output=True, text=True,
                          env=e, cwd=ROOT, timeout=60)


def test_version():
    r = run("--version")
    assert r.returncode == 0 and r.stdout.startswith("zone-timeline ")


def test_help_mentions_the_main_modes():
    r = run("--help")
    assert r.returncode == 0
    for flag in ("--line", "--json", "--once", "--markets", "--watch", "--reset"):
        assert flag in r.stdout


def test_json(tmp_path):
    r = run("--json", "--at", AT, env={"XDG_CONFIG_HOME": str(tmp_path)})
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["utc"] == "2026-03-18T14:30:00+00:00" and len(data["cities"]) == 9


def test_line_and_tmux(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    r = run("--line", "--at", AT, env=env)
    assert r.returncode == 0 and r.stdout.startswith("SF 07:30 · NY 10:30")
    r = run("--tmux", "--at", AT, "--seconds", env=env)
    assert "#[fg=#" in r.stdout and "07:30:00" in r.stdout


def test_once_renders_a_frame_of_the_requested_size(tmp_path):
    r = run("--once", "--size", "100x30", "--at", AT, env={"XDG_CONFIG_HOME": str(tmp_path)})
    assert r.returncode == 0
    lines = r.stdout.rstrip("\n").split("\n")
    assert len(lines) == 30 and all(len(ANSI.sub("", ln)) == 100 for ln in lines)
    assert "14:30:00 UTC" in ANSI.sub("", r.stdout)


def test_session_zones_and_labels_do_not_touch_the_config(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    r = run("--once", "--size", "120x30", "--at", AT, "Europe/Berlin", "Home=America/Chicago", env=env)
    text = ANSI.sub("", r.stdout)
    assert "Berlin" in text and "Home" in text and "Tokyo" not in text
    assert not (tmp_path / "zone-timeline").exists()


def test_unknown_place_is_an_error(tmp_path):
    r = run("--json", "Nope/Zone", env={"XDG_CONFIG_HOME": str(tmp_path)})
    assert r.returncode != 0 and "unknown place or time zone" in r.stderr


def test_reset(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    r = run("--reset", env=env)
    assert r.returncode == 0 and "nothing to reset" in r.stdout
    cfg = tmp_path / "zone-timeline" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{}")
    r = run("--reset", env=env)
    assert "removed" in r.stdout and not cfg.exists()


def test_interactive_mode_refuses_a_pipe(tmp_path):
    r = run(env={"XDG_CONFIG_HOME": str(tmp_path)})
    assert r.returncode != 0 and "needs an interactive terminal" in r.stderr
