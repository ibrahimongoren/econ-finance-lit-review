import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "econ-finance-lit-review"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from litrev_common import FILES, HEADERS, write_csv  # noqa: E402


def run(script: str, *args, cwd=None):
    """Run a bundled script; return (exit code, combined output)."""
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout + proc.stderr


@pytest.fixture
def folder(tmp_path):
    """An initialized, empty review folder."""
    code, out = run("init_review.py", "Test review", "--dir", tmp_path)
    assert code == 0, out
    return tmp_path / "litrev-test-review"


def rec(rid, title, authors, year, doi="", type_="journal-article", source="Crossref", query="Q1", venue="J"):
    return {"record_id": rid, "source": source, "query_id": query, "title": title, "authors": authors,
            "year": str(year), "venue": venue, "doi": doi, "type": type_}


def write(folder: Path, key: str, rows: list[dict]) -> None:
    write_csv(folder / FILES[key], rows, HEADERS[FILES[key]])


@pytest.fixture
def demo(tmp_path):
    """An initialized folder (window 2021-2026) filled with 12 synthetic included studies."""
    from demo_data import build_demo
    code, out = run("init_review.py", "Demo review", "--window", "2021-2026", "--dir", tmp_path)
    assert code == 0, out
    f = tmp_path / "litrev-demo-review"
    build_demo(f)
    return f
