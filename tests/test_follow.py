"""--follow is an ambient-view option: in non-interactive modes without
--ambient it used to be accepted and silently ignored (exit 0, no effect).
It must now be a usage error; with --ambient, or in interactive mode
(where it presets the ambient view), it stays accepted.
"""
import pytest

from terrahour import cli as cli_mod


def _run(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["terrahour", *argv])
    with pytest.raises(SystemExit) as exc:
        cli_mod.main()
    return exc.value.code


def test_follow_without_ambient_is_a_usage_error_in_once_mode(monkeypatch, capsys):
    assert _run(monkeypatch, "--once", "--follow", "9am") == 2
    assert "--follow" in capsys.readouterr().err


def test_follow_without_ambient_is_a_usage_error_in_line_mode(monkeypatch, capsys):
    assert _run(monkeypatch, "--line", "--follow", "9am") == 2


def test_follow_with_ambient_stays_accepted(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["terrahour", "--once", "--size", "100x30",
                                     "--ambient", "--follow", "9am",
                                     "--at", "2026-03-18T14:30:00Z"])
    cli_mod.main()  # must not raise
    assert "09:00 here" in capsys.readouterr().out
