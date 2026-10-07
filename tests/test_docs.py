"""The documentation must stay true: CLI.md matches --help, commands paste cleanly, community files line up."""

import importlib.util
import re

import pytest

from crossword_poster import cli
from tests.conftest import ROOT

yaml = pytest.importorskip("yaml")


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalise(text):
    """Whitespace-insensitive, and the same across Python versions (3.9 says 'optional arguments')."""
    return re.sub(r"\s+", " ", text.replace("optional arguments:", "options:")).strip()


# ----------------------------------------------------------------- CLI.md and --help
def test_cli_md_help_blocks_match_the_program():
    sync = load_script("sync_cli_docs")
    found = list(sync.blocks((ROOT / "docs" / "CLI.md").read_text(encoding="utf-8")))
    stale = [(cmd or "(top level)") for cmd, block in found if normalise(block) != normalise(sync.help_text(cmd))]
    assert not stale, f"docs/CLI.md is out of date for {stale}. Run: python scripts/sync_cli_docs.py"


def test_cli_md_has_a_help_block_for_every_command():
    sync = load_script("sync_cli_docs")
    documented = {cmd for cmd, _ in sync.blocks((ROOT / "docs" / "CLI.md").read_text(encoding="utf-8"))}
    expected = {None, *cli._commands()}
    assert documented == expected, f"missing: {expected - documented}, unknown: {documented - expected}"


def test_every_option_of_every_command_is_mentioned_in_cli_md():
    sync = load_script("sync_cli_docs")
    text = (ROOT / "docs" / "CLI.md").read_text(encoding="utf-8")
    missing = []
    for command in cli._commands():
        for option in sorted(set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", sync.help_text(command)))):
            if option not in text:
                missing.append(f"{command} {option}")
    assert not missing, missing


# ---------------------------------------------------------------- pasteable commands
def fenced_blocks(path):
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```(\w*)\n(.*?)```", text, re.S)


def test_no_user_command_in_the_docs_uses_a_line_continuation():
    # a trailing backslash fails in Windows Command Prompt and PowerShell: commands go on one line
    bad = []
    for path in [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md")]:
        for lang, body in fenced_blocks(path):
            if lang in ("bash", "bat", "powershell", "shell", "sh", "") and re.search(r"\\\n", body):
                bad.append(str(path.relative_to(ROOT)))
    assert not bad, bad


# --------------------------------------------------------------- community files
def test_issue_templates_use_labels_that_exist_on_every_new_repository():
    default_labels = {"bug", "enhancement", "documentation", "question"}
    for name in ("bug_report", "feature_request"):
        form = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / f"{name}.yml").read_text(encoding="utf-8"))
        assert set(form["labels"]) <= default_labels, (name, form["labels"])


def test_issue_chooser_links_to_the_default_qa_discussion_category():
    config = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8"))
    urls = [link["url"] for link in config["contact_links"]]
    assert "https://github.com/faramarz/crossword-poster/discussions/categories/q-a" in urls
    for path in [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *(ROOT / ".github").rglob("*.yml")]:
        text = path.read_text(encoding="utf-8")
        assert "discussions/categories/q-and-a" not in text, path


def test_codeowners_and_support_exist_and_point_to_the_right_places():
    assert (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").split()[-2:] == ["*", "@faramarz"]
    support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
    for needle in ("discussions/categories/q-a", "docs/TROUBLESHOOTING.md", "bug_report.yml"):
        assert needle in support


def test_every_relative_link_in_the_markdown_files_resolves():
    broken = []
    for path in [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md")]:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (path.parent / target).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, broken


# --------------------------------------------------------------------- release
def test_release_notes_come_from_the_changelog_section():
    notes = load_script("release_notes")
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\nNothing yet.\n\n## [1.2.0] - 2026-01-01\n\n### Added\n\n- A thing.\n\n"
        "## [1.1.0] - 2025-12-01\n\n- Older.\n\n[Unreleased]: https://example.com/compare\n"
    )
    assert notes.section(changelog, "1.2.0") == "### Added\n\n- A thing."
    assert notes.section(changelog, "1.1.0") == "- Older."
    assert notes.section(changelog, "9.9.9") == ""


def test_the_real_changelog_has_notes_for_the_current_version():
    import crossword_poster

    notes = load_script("release_notes")
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert notes.section(text, crossword_poster.__version__)


def test_release_workflow_is_least_privilege_and_does_not_publish_to_pypi():
    raw = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    wf = yaml.safe_load(raw)
    triggers = wf.get("on") or wf[True]
    assert triggers == {"push": {"tags": ["v*"]}}
    assert wf["permissions"] == {"contents": "read"}
    assert list(wf["jobs"]) == ["release"]
    assert wf["jobs"]["release"]["permissions"] == {"contents": "write"}
    assert "pypi" not in raw.lower() and "twine upload" not in raw
    assert "scripts/release_notes.py" in raw and "gh release create" in raw


def test_ci_workflow_has_read_only_permissions_and_a_package_job():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert ci["permissions"] == {"contents": "read"}
    assert "package" in ci["jobs"]
    steps = " ".join(str(s.get("run", "")) for s in ci["jobs"]["package"]["steps"])
    assert "twine check" in steps and "python -m build" in steps
    for name, job in ci["jobs"].items():
        assert "timeout-minutes" in job, name
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/setup-python"):
                assert step["with"].get("cache-dependency-path") == "pyproject.toml", name


def test_python_314_is_tested_and_listed():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert "3.14" in ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert "Programming Language :: Python :: 3.14" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "3.14" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_every_image_in_docs_is_used_by_a_page():
    pages = "\n".join(p.read_text(encoding="utf-8") for p in [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md")])
    unused = [p.name for p in (ROOT / "docs").glob("*.png") if p.name not in pages]
    assert not unused, unused


def test_the_claude_code_copy_of_the_skill_matches_the_source():
    """`.claude/skills/crossword-poster` is a plain copy (not a symlink: those break on Windows and in the sdist)."""
    src = ROOT / "skills" / "crossword-poster"
    copy = ROOT / ".claude" / "skills" / "crossword-poster"
    if not copy.exists():
        pytest.skip(".claude/ is not shipped in the source distribution")
    names = sorted(p.name for p in src.iterdir() if p.is_file())
    assert names == sorted(p.name for p in copy.iterdir() if p.is_file())
    for name in names:
        assert (copy / name).read_bytes() == (src / name).read_bytes(), (
            f"{name} differs; refresh the copy with: cp skills/crossword-poster/* .claude/skills/crossword-poster/"
        )
