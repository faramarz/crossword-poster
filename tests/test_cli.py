"""Command line behaviour: help, version, friendly errors (never a traceback), template, doctor."""

import csv
import sys

import pytest

from crossword_poster import __version__, cli, common, pipeline
from tests.conftest import write_csv


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_version(capsys):
    code, out, _ = run(capsys, "--version")
    assert code == 0
    assert out.strip() == f"crossword-poster {__version__}"


def test_no_arguments_prints_help_and_fails(capsys):
    code, out, _ = run(capsys)
    assert code == 2
    for command in ("build", "sample", "template", "doctor", "pool", "generate", "validate", "render", "verify"):
        assert command in out


def test_help_lists_exit_codes(capsys):
    code, out, _ = run(capsys, "--help")
    assert code == 0
    assert "Exit status" in out


def test_unknown_command_is_friendly(capsys):
    code, _, err = run(capsys, "biuld")
    assert code == 2
    assert "not a command" in err
    assert "build" in err
    assert "Traceback" not in err


def test_build_help_documents_every_option(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for option in ("--clues", "--title", "--subtitle", "--size", "--style", "--out", "--seed", "--require-all"):
        assert option in out
    assert "grey" in out and "black" in out and "icons" in out


def test_build_requires_clues(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["build"])
    assert exc.value.code == 2
    assert "--clues" in capsys.readouterr().err


def test_bad_style_is_rejected_by_argparse(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--clues", "x.csv", "--style", "rainbow"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("size", ["banana", "24", "0x36", "-1x5", "24x"])
def test_bad_size_is_a_friendly_error(capsys, small_csv, size):
    code, _, err = run(capsys, "build", "--clues", str(small_csv), f"--size={size}")
    assert code == 2
    assert "not a poster size" in err
    assert "WIDTHxHEIGHT" in err
    assert "Traceback" not in err


def test_missing_clues_file_is_a_friendly_error(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "check_chromium", lambda: (True, "fake"))
    code, _, err = run(capsys, "build", "--clues", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "o"))
    assert code == 2
    assert "File not found" in err
    assert "Traceback" not in err


def test_missing_column_is_a_friendly_error(capsys, tmp_path):
    path = write_csv(tmp_path / "x.csv", [("a", "b")], header=("foo", "bar"))
    code, _, err = run(capsys, "build", "--clues", str(path), "--out", str(tmp_path / "o"))
    assert code == 2
    assert "Could not find the clue column" in err
    assert "How to fix" in err


def test_build_stops_with_a_clear_message_when_chromium_is_missing(capsys, small_csv, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "check_chromium", lambda: (False, "no browser here"))
    code, _, err = run(capsys, "build", "--clues", str(small_csv), "--out", str(tmp_path / "o"))
    assert code == 3
    assert "crossword-poster install-browser" in err
    assert f'"{sys.executable}" -m playwright install chromium' in err
    assert "CROSSWORD_POSTER_CHROMIUM" in err


def test_require_all_fails_before_printing_anything(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "check_chromium", lambda: (True, "fake"))
    rows = [("Hot", "Planet"), ("Flows", "River"), ("Cat", "Tiger"), ("Odd one out", "Zzyzx")]
    path = write_csv(tmp_path / "x.csv", rows)
    out_dir = tmp_path / "poster"
    code, out, err = run(
        capsys,
        "build",
        "--clues",
        str(path),
        "--out",
        str(out_dir),
        "--attempts",
        "20",
        "--workers",
        "1",
        "--require-all",
    )
    assert code == 1
    assert "Zzyzx" in out
    assert "bigger --size" in out
    assert "--require-all" in err
    assert not list(out_dir.glob("*.pdf"))


def test_bad_options_values_are_caught(capsys, small_csv):
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--clues", str(small_csv), "--attempts", "many"])
    assert exc.value.code == 2


def test_template_writes_a_valid_starter_file(capsys, tmp_path):
    target = tmp_path / "sub" / "my_clues.csv"
    code, out, _ = run(capsys, "template", str(target))
    assert code == 0
    with open(target, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["id", "clue", "answer"]
    assert len(rows) == 4
    assert "crossword-poster build" in out
    # and the file it writes is accepted by the reader
    from crossword_poster import pool

    got, _ = pool.build_pool(str(target))
    assert len(got) == 3


def test_template_does_not_overwrite_without_force(capsys, tmp_path):
    target = tmp_path / "mine.csv"
    target.write_text("precious", encoding="utf-8")
    code, _, err = run(capsys, "template", str(target))
    assert code == 2
    assert "already exists" in err
    assert target.read_text(encoding="utf-8") == "precious"
    assert run(capsys, "template", str(target), "--force")[0] == 0
    assert target.read_text(encoding="utf-8-sig").startswith("id,clue,answer")


def test_pool_command_reports_problems(capsys, tmp_path):
    path = write_csv(
        tmp_path / "x.csv", [("Capital", "Paris"), ("Eternal city", "Rome"), ("Bad", "R2D2"), ("", "Ghost")]
    )
    code, out, _ = run(capsys, "pool", "--clues", str(path), "--out", str(tmp_path / "pool.csv"))
    assert code == 0
    assert "skipped row 4" in out and "digit" in out
    assert "skipped row 5" in out and "missing clue" in out


def test_doctor_reports_success_and_failure(capsys, monkeypatch):
    from crossword_poster import doctor

    monkeypatch.setattr(doctor, "check_chromium", lambda: (True, "Chromium 1.2.3"))
    code, out, _ = run(capsys, "doctor")
    assert code == 0
    assert "Chromium 1.2.3" in out and "Bundled fonts found" in out

    monkeypatch.setattr(doctor, "check_chromium", lambda: (False, "boom"))
    code, out, _ = run(capsys, "doctor")
    assert code == 1
    assert "crossword-poster install-browser" in out
    assert f'"{sys.executable}" -m playwright install chromium' in out
    assert "CROSSWORD_POSTER_CHROMIUM" in out


def test_unexpected_errors_are_summarised_not_dumped(capsys, monkeypatch):
    monkeypatch.delenv("CROSSWORD_POSTER_DEBUG", raising=False)
    monkeypatch.setattr(cli, "cmd_template", lambda argv: 1 / 0)
    code, _, err = run(capsys, "template", "x.csv")
    assert code == 70
    assert "Something unexpected" in err and "issues" in err
    assert "Traceback" not in err


# ---------------------------------------------------------- install-browser
def test_install_command_uses_this_python_and_quotes_it():
    cmd = common.install_command()
    assert cmd == [sys.executable, "-m", "playwright", "install", "chromium"]
    assert common.install_command_text().startswith(f'"{sys.executable}" -m playwright install chromium')
    assert common.install_command(with_deps=True)[-2:] == ["--with-deps", "chromium"]
    assert "--with-deps" in common.install_command_text(with_deps=True)


def test_install_command_text_quotes_a_path_with_spaces(monkeypatch):
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Python 3\python.exe")
    assert common.install_command_text() == r'"C:\Program Files\Python 3\python.exe" -m playwright install chromium'


def test_install_browser_runs_the_command_with_this_python(capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.subprocess, "call", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr(cli, "check_chromium", lambda: (True, "Chromium 9.9"))
    code, out, _ = run(capsys, "install-browser")
    assert code == 0
    assert calls == [[sys.executable, "-m", "playwright", "install", "chromium"]]
    assert "Chromium 9.9" in out


def test_install_browser_failure_is_friendly_and_shows_the_manual_command(capsys, monkeypatch):
    monkeypatch.setattr(cli.subprocess, "call", lambda cmd: 1)
    code, _, err = run(capsys, "install-browser", "--with-deps")
    assert code == 3
    assert "stopped with status 1" in err
    assert "--with-deps chromium" in err


def test_install_browser_is_listed_in_the_help(capsys):
    _, out, _ = run(capsys, "--help")
    assert "install-browser" in out


def test_build_help_documents_the_time_limit(capsys):
    with pytest.raises(SystemExit):
        cli.main(["build", "--help"])
    assert "--time-limit" in capsys.readouterr().out


# ------------------------------------------------------------- closed pipes
def test_broken_pipe_inside_a_command_exits_quietly(capsys, monkeypatch):
    def boom(argv):
        raise BrokenPipeError

    monkeypatch.setattr(cli, "_commands", lambda: {"doctor": boom})
    code, out, err = run(capsys, "doctor")
    assert code == 0
    assert out == "" and err == ""


def test_piping_into_a_reader_that_has_gone_prints_no_traceback():
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "-m", "crossword_poster", "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    proc.stdout.close()  # like `| head` after it has had enough
    err = proc.stderr.read()
    proc.wait(timeout=60)
    proc.stderr.close()
    assert b"Traceback" not in err and b"BrokenPipeError" not in err
