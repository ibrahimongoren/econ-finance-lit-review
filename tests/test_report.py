"""Figures, report assembly, DOCX/PDF build and the evidence workbook."""

import shutil
import zipfile

import pytest

import build_report
from conftest import run
from litrev_common import FILES

pytest.importorskip("matplotlib")

REPORT = """<!-- instructions that must disappear -->
# Kısa cevap

Bulgular karışık [3, 7].

{{TALLY}}

# 1. Kapsam

{{FIGURE:pipeline}}

{{FIGURE:prisma}}

{{FIGURE:foo}}

# 2. Zayıf yönler

{{FIGURE:weaknesses}}

{{WEAKNESS_TABLE}}

{{CARDS}}

{{REFERENCES}}
"""


def test_make_figures_writes_every_figure(demo):
    code, out = run("make_figures.py", demo, "--lang", "tr")
    assert code == 0, out
    for name in ("years", "map", "weaknesses", "regions", "sources", "pipeline"):
        path = demo / FILES["figures_dir"] / f"fig_{name}.png"
        assert path.exists() and path.stat().st_size > 10_000, name


def test_make_figures_skips_missing_data(folder):
    code, out = run("make_figures.py", folder, "--only", "years,weaknesses,pipeline")
    assert code == 0 and "skipped" in out
    assert (folder / FILES["figures_dir"] / "fig_pipeline.png").exists()


def test_assemble_expands_placeholders_and_contents(demo):
    (demo / FILES["report_md"]).write_text(REPORT, encoding="utf-8")
    run("make_figures.py", demo, "--lang", "tr")
    meta = {"title": 'Başlık "tırnaklı"', "subtitle": "Alt başlık", "author": "", "date": "20 Ekim 2026"}
    full, notes = build_report.assemble(demo, "tr", meta, toc=True)
    assert "{{" not in full and "<!--" not in full
    assert 'title: "Başlık \\"tırnaklı\\""' in full and "author:" not in full
    assert "Şekil 1. Tarama süreci" in full and "Şekil 2. Dahil edilen çalışmalarda" in full
    assert any("unknown figure 'foo'" in n for n in notes)
    assert any("figure 'prisma' not found" in n for n in notes)
    assert "| Literatür penceresi | 2021–2026 |" in full.replace("**", "")
    assert "12 (9 tam metinden, 3 yalnızca özetten okundu)" in full
    assert "**Doğrulama:** 11 doğrulandı" in full
    assert "# Çalışma kartları {#" in full and "### [1] " in full and "NEYİ EKSİK BIRAKMIŞ?" in full
    assert '::: {custom-style="Bibliography"}' in full and "# Kaynakça {#" in full
    assert "- [Kısa cevap](#sec-1)" in full and '::: {custom-style="TOC Heading"}' in full
    assert full.index("```{=openxml}") < full.index("# Kısa cevap")


def test_missing_report_md_fails(folder):
    (folder / FILES["report_md"]).unlink()
    code, out = run("build_report.py", folder, "--format", "docx")
    assert code == 1 and "not found" in out


def _docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        media = [n for n in z.namelist() if n.startswith("word/media/")]
        styles = z.read("word/styles.xml").decode("utf-8")
    return xml, media, styles


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_build_docx_with_pandoc(demo):
    pytest.importorskip("docx")
    run("prisma_flow.py", demo, "--lang", "tr")
    code, out = run("build_report.py", demo, "--format", "docx", "--lang", "tr", "--toc", "--title", "Deneme")
    assert code == 0 and "(pandoc)" in out, out
    xml, media, styles = _docx_text(demo / "10_report.docx")
    assert "NE YAPMIŞ?" in xml and "Kaynakça" in xml and "Deneme" in xml
    assert len(media) >= 7                                   # six figures + PRISMA
    assert "Bibliography" in styles and "1F3B57" in styles     # styled reference document
    code, out = run("audit_citations.py", demo / "10_report.docx", demo / FILES["verification"])
    assert code == 0, out


def test_build_docx_fallback_renderer(demo):
    pytest.importorskip("docx")
    code, out = run("build_report.py", demo, "--format", "docx", "--lang", "en", "--fallback", "--toc")
    assert code == 0 and "(python-docx)" in out, out
    xml, media, _ = _docx_text(demo / "10_report.docx")
    assert "WHAT DID IT DO?" in xml and len(media) >= 6


@pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice not installed")
def test_build_pdf_with_libreoffice(demo):
    pytest.importorskip("docx")
    code, out = run("build_report.py", demo, "--format", "pdf", "--lang", "tr", "--no-figures")
    assert code == 0, out
    pdf = demo / "10_report.pdf"
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"


def test_workbook_has_card_sheets(demo):
    openpyxl = pytest.importorskip("openpyxl")
    code, out = run("export_workbook.py", demo)
    assert code == 0, out
    wb = openpyxl.load_workbook(demo / "evidence_workbook.xlsx")
    assert {"Study cards", "Weaknesses", "Full text", "Verification"} <= set(wb.sheetnames)
    assert wb["Study cards"]["B2"].alignment.wrap_text
