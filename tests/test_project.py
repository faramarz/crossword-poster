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
    assert set(ci["jobs"]) == {"lint", "test", "e2e", "smoke", "package"}
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix == ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]
    assert set(ci["jobs"]["smoke"]["strategy"]["matrix"]["os"]) == {"macos-latest", "windows-latest"}
    commands = " ".join(str(s.get("run", "")) for s in ci["jobs"]["e2e"]["steps"])
    assert "crossword-poster install-browser --with-deps" in commands
    smoke = " ".join(str(s.get("run", "")) for s in ci["jobs"]["smoke"]["steps"])
    assert "crossword-poster install-browser" in smoke and "crossword-poster sample" in smoke
    assert (ci.get("on") or ci[True])["push"]["branches"] == ["main"]  # YAML reads a bare `on` as True
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


# ------------------------------------------------------------ install instructions
INSTALL_LINE = re.compile(r"\b(pip3?|pipx|uv tool|uv pip) install\b")


def install_instruction_lines():
    """Every line of the package and the docs that tells a person to install something."""
    files = [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *(ROOT / "crossword_poster").glob("*.py")]
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if INSTALL_LINE.search(line):
                yield path.relative_to(ROOT), n, line


def test_no_instruction_installs_crossword_poster_from_pypi():
    # the package is not on PyPI: installing "crossword-poster" by name would fail, or fetch somebody else's package
    bad = [
        f"{path}:{n}: {line.strip()}"
        for path, n, line in install_instruction_lines()
        if re.search(r"crossword-poster\b", line) and "git+" not in line and "archive/refs/" not in line
    ]
    assert not bad, "install from GitHub, not by name:\n" + "\n".join(bad)


def test_install_hints_in_error_messages_use_the_github_url():
    from crossword_poster import common

    assert (
        common.REINSTALL_HINT
        == "pip install --upgrade --force-reinstall git+https://github.com/faramarz/crossword-poster"
    )
    assert common.XLSX_HINT.startswith('pip install "crossword-poster[xlsx] @ git+https://github.com/faramarz/')


def test_the_xlsx_hint_is_valid_pep_508():
    packaging = pytest.importorskip("packaging.requirements")
    from crossword_poster import common

    spec = re.search(r'"(.+?)"', common.XLSX_HINT).group(1)
    req = packaging.Requirement(spec)
    assert req.name == "crossword-poster" and req.extras == {"xlsx"}
    assert req.url == "git+" + common.REPO_URL
