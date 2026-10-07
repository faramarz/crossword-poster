"""Repository hygiene: valid CI files, one version source, packaged data, no hard-coded paths."""

import re
from importlib import metadata, resources
from pathlib import Path

import pytest

import crossword_poster
from tests.conftest import ROOT, SAMPLE_BIRTHDAY

yaml = pytest.importorskip("yaml")


def load(path):
    with open(ROOT / path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_ci_workflow_is_valid_and_complete():
    ci = load(".github/workflows/ci.yml")
    assert set(ci["jobs"]) == {"lint", "test", "e2e", "smoke"}
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix == ["3.9", "3.10", "3.11", "3.12", "3.13"]
    assert set(ci["jobs"]["smoke"]["strategy"]["matrix"]["os"]) == {"macos-latest", "windows-latest"}
    commands = " ".join(str(s.get("run", "")) for s in ci["jobs"]["e2e"]["steps"])
    assert "playwright install --with-deps chromium" in commands
    lint = " ".join(str(s.get("run", "")) for s in ci["jobs"]["lint"]["steps"])
    assert "ruff check" in lint and "ruff format --check" in lint


def test_ci_actions_are_pinned_to_major_versions():
    ci = load(".github/workflows/ci.yml")
    for job in ci["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w./-]+@v\d+", step["uses"]), step["uses"]


def test_dependabot_covers_pip_and_actions_monthly():
    cfg = load(".github/dependabot.yml")
    ecosystems = {u["package-ecosystem"]: u["schedule"]["interval"] for u in cfg["updates"]}
    assert ecosystems == {"pip": "monthly", "github-actions": "monthly"}


def test_version_has_a_single_source():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in pyproject
    assert not re.search(r"^version\s*=", pyproject, re.M)
    assert re.fullmatch(r"\d+\.\d+\.\d+", crossword_poster.__version__)
    try:
        installed = metadata.version("crossword-poster")
    except metadata.PackageNotFoundError:
        pytest.skip("package is not installed")
    assert installed == crossword_poster.__version__


def test_fonts_ship_as_package_data():
    base = resources.files("crossword_poster").joinpath("fonts")
    for family, filename in [("ArchivoNarrow", "ArchivoNarrow-Bold.ttf"), ("Oswald", "Oswald-Bold.ttf")]:
        assert base.joinpath(family, filename).is_file()
        assert base.joinpath(family, "OFL.txt").is_file()


def test_every_bundled_font_listed_is_present():
    from crossword_poster.common import missing_fonts

    assert missing_fonts() == []


def test_examples_copy_of_the_birthday_sample_matches_the_packaged_one():
    assert (ROOT / "examples" / "sample_birthday.csv").read_bytes() == SAMPLE_BIRTHDAY.read_bytes()


def test_no_pymupdf_anywhere():
    offenders = []
    for path in list((ROOT / "crossword_poster").rglob("*.py")) + [ROOT / "pyproject.toml"]:
        text = path.read_text(encoding="utf-8").lower()
        if "pymupdf" in text or "import fitz" in text:
            offenders.append(path.name)
    assert offenders == []


def test_no_hard_coded_user_paths_in_the_package():
    pattern = re.compile(r"(/home/|/Users/|/tmp/|C:\\\\Users)")
    offenders = [
        p.name for p in (ROOT / "crossword_poster").rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_licence_files_exist():
    for name in ("LICENSE", "THIRD_PARTY_LICENSES.md"):
        assert (Path(ROOT) / name).stat().st_size > 500
    assert "MIT" in (ROOT / "LICENSE").read_text(encoding="utf-8")
