"""Reference formatting, citation audit and the verification match logic."""

import zipfile

import pytest

import verify_refs as v
from conftest import SKILL, run
from litrev_common import FILES, HEADERS, write_csv

EXAMPLE = SKILL / "references" / "example_verification.csv"


def test_reference_list_from_verified_examples():
    code, out = run("format_references.py", EXAMPLE, "--lang", "en")
    assert code == 0, out
    assert ("Andrews, I., & Kasy, M. (2019). Identification of and correction for publication bias. "
            "*American Economic Review, 109*(8), 2766–2794. https://doi.org/10.1257/aer.20180310") in out
    # 26 authors -> first 19, ellipsis, last author (APA 7)
    assert "McDonald, S., . . . Moher, D. (2021)" in out
    # group author keeps its own period
    assert "Koffel, J. B., & PRISMA-S Group. (2021)" in out
    assert "printed 15 entries" in out and "0 warning(s)" in out


def test_turkish_connector():
    code, out = run("format_references.py", EXAMPLE, "--lang", "tr")
    assert "Andrews, I. ve Kasy, M. (2019)." in out
    assert "## Kaynakça" in out


def test_formatter_blocks_unverified_and_warns(tmp_path):
    rows = [
        {"ref_id": "Ok2020", "status": "VERIFIED", "authors": "Ok, Ada; Et Al, X.", "year": "2020",
         "title": "A TITLE IN CAPITALS ONLY", "venue": "J", "doi": "10.1/ok", "type": "journal-article"},
        {"ref_id": "Bad2021", "status": "NOT_VERIFIED", "authors": "Bad, B.", "year": "2021", "title": "Ghost"},
    ]
    path = tmp_path / "v.csv"
    write_csv(path, rows, HEADERS[FILES["verification"]])
    code, out = run("format_references.py", path, "--include-unverified")
    assert "Ghost" in out.split("Unverified or retracted")[1]
    assert "link check method/date missing" in out
    assert "ALL CAPS" in out


def _report_fixture(tmp_path):
    rows = [
        {"ref_id": "Andrews2019", "status": "VERIFIED", "authors": "Andrews, Isaiah; Kasy, Maximilian",
         "year": "2019", "doi": "10.1257/aer.20180310", "link_check_method": "doi.org", "checked_on": "2026-10-08"},
        {"ref_id": "Garcia2021", "status": "VERIFIED", "authors": "García, Ana; López, Juan", "year": "2021",
         "link": "https://example.org/p", "link_check_method": "page", "checked_on": "2026-10-08"},
        {"ref_id": "Mercan2020", "status": "VERIFIED", "authors": "Mercan, Derya; Canbay, Şerif", "year": "2020",
         "link": "https://dergipark.org.tr/x", "link_check_method": "page", "checked_on": "2026-10-08"},
        {"ref_id": "Ghost2022", "status": "NOT_VERIFIED", "authors": "Ghost, G.", "year": "2022"},
        {"ref_id": "NoLink2018", "status": "VERIFIED", "authors": "Nolink, Z.", "year": "2018"},
    ]
    ver = tmp_path / "05.csv"
    write_csv(ver, rows, HEADERS[FILES["verification"]])
    return ver


def test_audit_flags_blocking_problems(tmp_path):
    ver = _report_fixture(tmp_path)
    report = tmp_path / "10_report.md"
    report.write_text(
        "Bias is common (Andrews & Kasy, 2019; see García y López, 2021).\n"
        "Mercan ve Canbay'a (2020) göre kredi kanalı işler. Table 2 (2019) is not a citation.\n"
        "Unknown work (Smith, 2015) and a ghost (Ghost, 2022).\n\n## References\n\nSmith, J. (2015).\n",
        encoding="utf-8")
    code, out = run("audit_citations.py", report, ver)
    assert code == 1
    no_entry = out.split("no entry in the verification log:")[1].split("BLOCKING")[0]
    assert "Smith (2015)" in no_entry and "Table" not in no_entry
    assert "Ghost (2022)" in out.split("NOT_VERIFIED / RETRACTED source:")[1]
    assert "NoLink2018: no DOI or link" in out


def test_audit_passes_clean_docx(tmp_path):
    ver = _report_fixture(tmp_path)
    rows = [r for r in __import__("litrev_common").read_csv(ver) if r["ref_id"] in ("Andrews2019", "Garcia2021")]
    write_csv(ver, rows, HEADERS[FILES["verification"]])
    docx = tmp_path / "r.docx"
    body = ('<w:document><w:body><w:p><w:r><w:t>Evidence (Andrews &amp; Kasy, 2019) and '
            'García et al. (2021).</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", body)
    code, out = run("audit_citations.py", docx, ver, "--strict")
    assert code == 0, out
    assert "RESULT: PASS" in out


def test_verify_refs_selftest():
    code, out = run("verify_refs.py", "--selftest")
    assert code == 0 and out.count("PASS") == 4


class _MockClient(v.Client):
    WORK = {"DOI": "10.1111/joes.12595",
            "title": ["Meta‐analysis of social science research: A practitioner's guide"],
            "author": [{"given": "Zuzana", "family": "Iršová"}, {"given": "Hristos", "family": "Doucouliagos"}],
            "issued": {"date-parts": [[2023, 11, 23]]}, "published-print": {"date-parts": [[2024, 12]]},
            "published-online": {"date-parts": [[2023, 11, 23]]}, "container-title": ["Journal of Economic Surveys"],
            "volume": "38", "issue": "5", "page": "1547-1566", "type": "journal-article"}

    def get_json(self, url, tries=3):
        if "query.bibliographic" in url:
            return {"message": {"items": [{"DOI": "10.9/x", "title": ["Unrelated"], "author": [{"family": "Other"}],
                                           "issued": {"date-parts": [[2020]]}}, self.WORK]}}
        if "api.crossref.org/works/" in url:
            return {"message": self.WORK} if "joes.12595" in url.lower() else None
        if "openalex" in url:
            return {"is_retracted": False, "is_paratext": False, "open_access": {"oa_url": None}}
        if "doi.org/api/handles" in url:
            return {"responseCode": 1}
        return None


@pytest.mark.parametrize("src,status", [
    ({"ref_id": "A", "doi": "https://doi.org/10.1111/JOES.12595", "title": "Meta-analysis of social science "
      "research: a practitioner's guide", "authors": "Irsova, Z.", "year": "2024"}, "VERIFIED"),
    ({"ref_id": "B", "title": "Meta-analysis of social science research: A practitioner’s guide",
      "authors": "Iršová, Zuzana", "year": "2023"}, "VERIFIED"),
    ({"ref_id": "C", "title": "Meta-analysis of social science research", "authors": "Smith, John",
      "year": "2010"}, "NOT_VERIFIED"),
    ({"ref_id": "D", "doi": "10.1111/joes.99999", "title": "Invented paper", "authors": "Nobody, N.",
      "year": "2020"}, "NOT_VERIFIED"),
])
def test_verify_row_with_mocked_registries(src, status):
    out = v.verify_row(_MockClient("t@example.org", 0), src, True)
    assert out["status"] == status
    if status == "VERIFIED":
        assert out["year"] == 2024 and out["online_year"] == 2023
        assert out["link"] == "https://doi.org/10.1111/joes.12595"
