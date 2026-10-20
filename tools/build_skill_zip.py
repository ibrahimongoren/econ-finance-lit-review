#!/usr/bin/env python3
"""Build the uploadable skill archive for Claude apps.

Usage:
    python tools/build_skill_zip.py            # -> dist/econ-finance-lit-review.zip

The archive contains the skill folder itself as its top level
(econ-finance-lit-review/SKILL.md, references/, scripts/), which is the layout the
Claude apps expect when you upload a skill under Customize > Skills. Caches and
compiled files are left out. Runs on Windows, macOS and Linux (standard library only).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "econ-finance-lit-review"
DIST = ROOT / "dist"
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def main() -> int:
    if not (SKILL / "SKILL.md").exists():
        print(f"SKILL.md not found under {SKILL}")
        return 1
    DIST.mkdir(exist_ok=True)
    out = DIST / f"{SKILL.name}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL.rglob("*")):
            rel = path.relative_to(SKILL.parent)
            if not path.is_file() or any(p in SKIP_DIRS for p in rel.parts):
                continue
            if path.suffix in SKIP_SUFFIXES or path.name in SKIP_NAMES:
                continue
            zf.write(path, rel.as_posix())
            count += 1
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    bad = [n for n in names if not n.startswith(f"{SKILL.name}/")]
    if bad or f"{SKILL.name}/SKILL.md" not in names:
        print("Archive layout is wrong:", bad[:5])
        return 1
    print(f"Wrote {out} ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
