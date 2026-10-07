"""Feedback channels: the form link, the `feedback` command and the one-line nudge after a successful build."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from crossword_poster import __version__, cli, feedback, pipeline

ROOT = Path(__file__).resolve().parent.parent
NUDGE = (
    "Made a poster? Tell us how it went: crossword-poster feedback  "
    "(or https://github.com/faramarz/crossword-poster/issues/new?template=feedback.yml)"
)


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(feedback.NO_HINT_ENV, raising=False)


# ------------------------------------------------------------------- the link
def test_feedback_url_has_template_version_and_os_encoded():
    url = feedback.feedback_url(version="1.2.3", os_summary="macOS 15.1 (arm64), Python 3.13.1")
    parts = urlparse(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://github.com/faramarz/crossword-poster/issues/new"
    query = parse_qs(parts.query)
    assert query == {
        "template": ["feedback.yml"],
        "version": ["1.2.3"],
        "os": ["macOS 15.1 (arm64), Python 3.13.1"],
    }
    assert " " not in url and "(" not in url  # really encoded, not pasted in


def test_feedback_url_defaults_to_this_program_and_computer():
    query = parse_qs(urlparse(feedback.feedback_url()).query)
    assert query["version"] == [__version__]
    assert query["os"] == [feedback.platform_summary()]
    assert "Python" in query["os"][0]


def test_platform_summary_looks_like_a_description(monkeypatch):
    monkeypatch.setattr(feedback.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(feedback.platform, "mac_ver", lambda: ("15.1", ("", "", ""), "arm64"))
    monkeypatch.setattr(feedback.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(feedback.platform, "python_version", lambda: "3.13.1")
    assert feedback.platform_summary() == "macOS 15.1 (arm64), Python 3.13.1"


def test_issue_form_has_the_fields_the_link_fills_in():
    form = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "feedback.yml").read_text(encoding="utf-8"))
    assert form["labels"] == ["feedback"]
    ids = {item["id"] for item in form["body"] if "id" in item}
    assert {"how_it_went", "occasion", "what_worked", "what_to_improve", "version", "os", "photo"} <= ids
    config = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8"))
    urls = [link["url"] for link in config["contact_links"]]
    assert "mailto:gm@faramarz.xyz" in urls
    assert "https://github.com/faramarz/crossword-poster/discussions/categories/show-and-tell" in urls


# ---------------------------------------------------------------- the command
def test_feedback_no_open_prints_links_and_does_not_open_a_browser(capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the browser must not be opened with --no-open")

    monkeypatch.setattr(feedback.webbrowser, "open", boom)
    code, out, _ = run(capsys, "feedback", "--no-open")
    assert code == 0
    assert feedback.feedback_url() in out
    assert feedback.FEEDBACK_EMAIL in out
    assert feedback.SHOW_AND_TELL_URL in out
    assert "template=feedback.yml" in out


def test_feedback_opens_the_form_in_the_browser(capsys, monkeypatch):
    opened = []
    monkeypatch.setattr(feedback, "_has_display", lambda: True)
    monkeypatch.setattr(feedback.webbrowser, "open", lambda url: opened.append(url) or True)
    code, out, _ = run(capsys, "feedback")
    assert code == 0
    assert opened == [feedback.feedback_url()]
    assert feedback.FEEDBACK_EMAIL in out


def test_feedback_survives_a_browser_that_cannot_open(capsys, monkeypatch):
    def broken(url):
        raise RuntimeError("no browser")

    monkeypatch.setattr(feedback, "_has_display", lambda: True)
    monkeypatch.setattr(feedback.webbrowser, "open", broken)
    code, out, err = run(capsys, "feedback")
    assert code == 0
    assert feedback.feedback_url() in out
    assert "Traceback" not in out + err


def test_feedback_without_a_screen_only_prints(capsys, monkeypatch):
    monkeypatch.setattr(feedback, "_has_display", lambda: False)
    monkeypatch.setattr(feedback.webbrowser, "open", lambda url: pytest.fail("no screen: must not open"))
    code, out, _ = run(capsys, "feedback")
    assert code == 0
    assert feedback.feedback_url() in out


def test_feedback_is_in_the_top_help_and_says_it_sends_nothing(capsys):
    _, out, _ = run(capsys, "--help")
    assert "feedback" in out
    with pytest.raises(SystemExit):
        cli.main(["feedback", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "sends nothing" in text and "never reads your clues" in text


# ------------------------------------------------------------------ the nudge
@pytest.fixture
def fake_build(monkeypatch):
    """Replace the real build (which needs Chromium) with one that succeeds or fails on demand."""
    state = {"ok": True}

    def build(opts, *a, **k):
        print("Done in 1s.")
        return pipeline.BuildResult(out=opts.out, checks_ok=state["ok"])

    monkeypatch.setattr(cli, "build", build)
    return state


def test_nudge_follows_a_successful_sample(capsys, tmp_path, fake_build):
    code, out, _ = run(capsys, "sample", "--out", str(tmp_path / "s"))
    assert code == 0
    assert out.rstrip().splitlines()[-1] == NUDGE
    assert feedback.hint_text() == NUDGE


def test_nudge_follows_a_successful_build(capsys, tmp_path, small_csv, fake_build):
    code, out, _ = run(capsys, "build", "--clues", str(small_csv), "--out", str(tmp_path / "o"))
    assert code == 0
    assert out.rstrip().splitlines()[-1] == NUDGE


@pytest.mark.parametrize("command", ["sample", "build"])
def test_nudge_is_hidden_by_the_flag(capsys, tmp_path, small_csv, fake_build, command):
    args = ["sample"] if command == "sample" else ["build", "--clues", str(small_csv)]
    code, out, _ = run(capsys, *args, "--out", str(tmp_path / "o"), "--no-feedback-hint")
    assert code == 0
    assert "crossword-poster feedback" not in out


@pytest.mark.parametrize("command", ["sample", "build"])
def test_nudge_is_hidden_by_the_environment_variable(capsys, tmp_path, small_csv, fake_build, monkeypatch, command):
    monkeypatch.setenv("CROSSWORD_POSTER_NO_FEEDBACK", "1")
    args = ["sample"] if command == "sample" else ["build", "--clues", str(small_csv)]
    code, out, _ = run(capsys, *args, "--out", str(tmp_path / "o"))
    assert code == 0
    assert "crossword-poster feedback" not in out


def test_environment_variable_zero_does_not_hide_the_nudge(capsys, tmp_path, fake_build, monkeypatch):
    monkeypatch.setenv("CROSSWORD_POSTER_NO_FEEDBACK", "0")
    _, out, _ = run(capsys, "sample", "--out", str(tmp_path / "o"))
    assert NUDGE in out


@pytest.mark.parametrize("command", ["sample", "build"])
def test_no_nudge_when_checks_fail(capsys, tmp_path, small_csv, fake_build, command):
    fake_build["ok"] = False
    args = ["sample"] if command == "sample" else ["build", "--clues", str(small_csv)]
    code, out, _ = run(capsys, *args, "--out", str(tmp_path / "o"))
    assert code == 1
    assert "crossword-poster feedback" not in out


def test_no_nudge_when_the_build_fails(capsys, tmp_path, small_csv, monkeypatch):
    def failing(opts, *a, **k):
        raise cli.UserError("bad input", "fix it")

    monkeypatch.setattr(cli, "build", failing)
    code, out, err = run(capsys, "build", "--clues", str(small_csv), "--out", str(tmp_path / "o"))
    assert code == 2
    assert "crossword-poster feedback" not in out + err


def test_other_commands_do_not_print_the_nudge(capsys, tmp_path):
    code, out, _ = run(capsys, "template", str(tmp_path / "t.csv"))
    assert code == 0
    assert "Made a poster?" not in out


def test_both_ways_to_hide_the_nudge_are_in_the_help(capsys):
    for command in ("build", "sample"):
        with pytest.raises(SystemExit):
            cli.main([command, "--help"])
        text = " ".join(capsys.readouterr().out.split())
        assert "--no-feedback-hint" in text and "CROSSWORD_POSTER_NO_FEEDBACK=1" in text
