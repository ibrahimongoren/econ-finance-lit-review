#!/usr/bin/env python3
"""Replace the YOUR_GITHUB_USERNAME placeholder with your GitHub user or organization.

Usage (run once, from the repository root, before the first push):
    python tools/set_github_owner.py <github-username>

Edits the files listed in FILES in place (README, citation metadata, contributing guide,
plugin manifest, issue-form configuration) and prints the number of replacements per file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "YOUR_GITHUB_USERNAME"
FILES = [
    "README.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    ".claude-plugin/plugin.json",
    ".github/ISSUE_TEMPLATE/config.yml",
]


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", args[0]):
        print(__doc__)
        return 1
    owner = args[0]
    for name in FILES:
        path = root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        n = text.count(PLACEHOLDER)
        if n:
            path.write_text(text.replace(PLACEHOLDER, owner), encoding="utf-8")
        print(f"{name}: {n} replacement(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
