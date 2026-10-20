"""Structure checks: frontmatter, referenced files, manifests and the uploadable archive."""

import json
import re
import subprocess
import sys
import zipfile

import pytest

from conftest import ROOT, SKILL

yaml = pytest.importorskip("yaml")


def frontmatter():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    return yaml.safe_load(m.group(1)), text


def test_frontmatter_follows_the_agent_skills_limits():
    fm, text = frontmatter()
    assert fm["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 0 < len(fm["description"]) <= 1024
    assert "<" not in fm["description"] and ">" not in fm["description"]
    assert len(fm.get("compatibility", "")) <= 500
    assert len(text.splitlines()) < 500, "keep SKILL.md under 500 lines"


def test_every_referenced_file_exists():
    _, text = frontmatter()
    for ref in set(re.findall(r"`?((?:references|scripts)/[\w.\-]+\.(?:md|py|csv))`?", text)):
        assert (SKILL / ref).exists(), ref
    for ref in set(re.findall(r"`([\w\-]+\.py)`", text)):
        assert (SKILL / "scripts" / ref).exists(), ref


def test_manifests_agree():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    fm, _ = frontmatter()
    entry = market["plugins"][0]
    assert plugin["name"] == entry["name"] == SKILL.name
    assert plugin["version"] == str(fm["metadata"]["version"])
    assert entry["source"] == "./"
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {plugin['version']}" in cff


def test_build_zip_layout(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_skill_zip.py")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    with zipfile.ZipFile(ROOT / "dist" / f"{SKILL.name}.zip") as z:
        names = z.namelist()
    assert f"{SKILL.name}/SKILL.md" in names
    assert all(n.startswith(f"{SKILL.name}/") for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)


def test_readme_figures_exist_and_match_the_generator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_readme_figures", ROOT / "tools" / "make_readme_figures.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|srcset)="(docs/assets/[^"]+)"', text)
    assert len(refs) >= 9
    for ref in refs:
        assert (ROOT / ref).exists(), ref
    for fig, fn in gen.FIGURES.items():
        for theme in ("light", "dark"):
            path = ROOT / "docs" / "assets" / f"{fig}-en-{theme}.svg"
            assert path.read_text(encoding="utf-8") == fn("en", theme), f"regenerate {path.name}"


DOCS = ("README.md", "integrations/README.md", "CONTRIBUTING.md", "SECURITY.md",
        "CODE_OF_CONDUCT.md", "CHANGELOG.md")


def test_relative_links_in_documentation_resolve():
    for name in DOCS:
        doc = ROOT / name
        text = doc.read_text(encoding="utf-8")
        targets = re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text) + re.findall(r'(?:src|srcset|href)="([^"#:]+)"', text)
        for target in targets:
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            assert (doc.parent / target).exists(), f"{name}: broken link {target}"


def github_anchor(heading):
    """Anchor GitHub generates for a Markdown heading (lower case, punctuation dropped)."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def test_readme_contents_links_match_headings():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    anchors = {github_anchor(h) for h in re.findall(r"^#{1,6} (.+)$", body, re.M)}
    links = re.findall(r"\]\(#([^)]+)\)", text)
    assert len(links) >= 12
    for link in links:
        assert link in anchors, f"README contents link #{link} has no matching heading"


def test_issue_forms_are_well_formed():
    folder = ROOT / ".github" / "ISSUE_TEMPLATE"
    forms = sorted(p for p in folder.glob("*.yml") if p.name != "config.yml")
    assert len(forms) >= 3
    for path in forms:
        form = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert form["name"] and form["description"], path.name
        ids = [item["id"] for item in form["body"] if "id" in item]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate ids"
        for item in form["body"]:
            assert item["type"] in {"markdown", "input", "textarea", "dropdown", "checkboxes"}
            assert item["attributes"].get("label") or item["type"] == "markdown", path.name
    config = yaml.safe_load((folder / "config.yml").read_text(encoding="utf-8"))
    assert isinstance(config["blank_issues_enabled"], bool)


def test_owner_tool_covers_every_placeholder(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("set_github_owner", ROOT / "tools" / "set_github_owner.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    skip = {".git", "dist", "tools", "tests", "__pycache__", ".pytest_cache"}
    found = set()
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if path.is_file() and not skip.intersection(rel.parts) and path.suffix not in {".png", ".zip", ".skill"}:
            if tool.PLACEHOLDER in path.read_text(encoding="utf-8", errors="ignore"):
                found.add(rel.as_posix())
    # Passes both before and after the owner has been set (then no placeholder is left).
    assert found <= set(tool.FILES), f"add to FILES: {sorted(found - set(tool.FILES))}"
    for name in tool.FILES:
        assert (ROOT / name).exists(), name
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"url: https://github.com/{tool.PLACEHOLDER}/econ-finance-lit-review\n", encoding="utf-8")
    assert tool.main(["example-org"], root=tmp_path) == 0
    for name in tool.FILES:
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert tool.PLACEHOLDER not in text and "example-org" in text, name
