"""Print the CHANGELOG.md section of one version (the text of a GitHub Release).

    python scripts/release_notes.py 1.0.0 [CHANGELOG.md]

Exits with status 1 and a message when the version has no section or the section is empty.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def section(changelog: str, version: str) -> str:
    """The body of ``## [version] ...`` up to the next ``## [`` heading (or the link references at the end)."""
    lines = changelog.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(rf"##\s*\[{re.escape(version)}\]", ln)), None)
    if start is None:
        return ""
    body = []
    for ln in lines[start + 1 :]:
        if ln.startswith("## [") or re.match(r"\[[^\]]+\]:\s*https?://", ln):
            break
        body.append(ln)
    return "\n".join(body).strip()


def main(argv: list[str]) -> int:
    """Command line entry point."""
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    version = argv[0].lstrip("v")
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    text = section(path.read_text(encoding="utf-8"), version)
    if not text:
        print(f"{path} has no non-empty section for version {version}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
