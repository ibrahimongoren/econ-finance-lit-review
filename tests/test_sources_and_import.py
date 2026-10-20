"""Database search adapters (mocked HTTP), query translation, imports and open-access look-ups."""

import json
import urllib.parse

import pytest

import find_fulltext
import import_records
import search_sources as ss
from conftest import run, write
from litrev_common import FILES, read_csv

Q = '("phillips curve" OR "inflation dynamics") AND (regime OR threshold) NOT survey'
W = (2021, 2026)


# ---------------------------------------------------------------------------
# Query translation
# ---------------------------------------------------------------------------
def test_translations():
    assert ss.to_scopus(Q).startswith('TITLE-ABS-KEY(( "phillips curve" OR')
    assert "AND NOT survey" in ss.to_scopus(Q)
    assert ss.to_wos(Q, W).endswith("AND PY=(2021-2026)") and ss.to_wos(Q, W).startswith("TS=(")
    s2 = ss.to_s2(Q)
    assert '"phillips curve" | "inflation dynamics"' in s2 and "+ (" in s2 and s2.endswith("-survey")
    assert "survey" not in ss.to_crossref(Q) and "phillips curve" in ss.to_crossref(Q)
    ax = ss.to_arxiv('"phillips curve" regime NOT survey')
    assert ax == 'all:"phillips curve" AND all:regime ANDNOT all:survey'
    assert ss.to_scholar(Q).endswith("-survey")
    web = ss.web_interface_queries(Q, W)
    assert "PUBYEAR > 2020 AND PUBYEAR < 2027" in web["Scopus (Advanced document search)"]


def test_family_first_names():
    assert ss.family_first("Jane van der Berg") == "van der Berg, Jane"
    assert ss.family_first("Doe, Jane") == "Doe, Jane"
    assert ss.family_first("Plato") == "Plato"


# ---------------------------------------------------------------------------
# Mocked APIs
# ---------------------------------------------------------------------------
ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v2</id>
    <published>2024-01-02T00:00:00Z</published>
    <title>Regime-dependent inflation
      persistence</title>
    <summary>We study regimes.</summary>
    <author><name>Ana Lopez</name></author>
    <author><name>Wei Chen</name></author>
    <link href="http://arxiv.org/abs/2401.00001v2" rel="alternate" type="text/html"/>
    <arxiv:doi>10.5555/arx.1</arxiv:doi>
  </entry>
</feed>"""

PAYLOADS = {
    "api.openalex.org": {"meta": {"count": 1}, "results": [{
        "display_name": "Oil shocks and inflation regimes", "publication_year": 2023,
        "authorships": [{"author": {"display_name": "Jane van der Berg"}}, {"author": {"display_name": "Ali Kaya"}}],
        "primary_location": {"source": {"display_name": "Energy Economics"}},
        "biblio": {"volume": "120", "issue": "1", "first_page": "1", "last_page": "20"},
        "doi": "https://doi.org/10.5555/OA.1", "id": "https://openalex.org/W1", "type": "article",
        "abstract_inverted_index": {"Oil": [0], "matters": [1]}, "cited_by_count": 4,
        "open_access": {"oa_url": "https://example.org/oa.pdf"}}]},
    "api.crossref.org": {"message": {"total-results": 1, "next-cursor": "c2", "items": [{
        "DOI": "10.5555/CR.1", "title": ["Hybrid NKPC in emerging markets"], "type": "journal-article",
        "author": [{"given": "Ayşe", "family": "Demir"}], "issued": {"date-parts": [[2022, 3]]},
        "container-title": ["Applied Economics"], "volume": "54", "page": "1-10",
        "abstract": "<jats:p>Tagged abstract.</jats:p>"}]}},
    "api.semanticscholar.org": {"total": 1, "token": None, "data": [{
        "title": "Geopolitical risk and inflation", "year": 2024, "authors": [{"name": "Dario Caldara"}],
        "externalIds": {"DOI": "10.5555/S2.1", "ArXiv": "2401.1"}, "venue": "", "journal": {"name": "J. Intl. Econ."},
        "url": "https://www.semanticscholar.org/paper/x", "publicationTypes": ["JournalArticle"],
        "citationCount": 9, "openAccessPdf": {"url": "https://example.org/s2.pdf"}}]},
    "export.arxiv.org": ATOM,
    "api.elsevier.com/content/search/scopus": {"search-results": {"opensearch:totalResults": "1", "entry": [{
        "dc:title": "Climate risk and prices", "prism:coverDate": "2025-02-01", "dc:creator": "Smith J.",
        "prism:publicationName": "Energy Policy", "prism:volume": "9", "prism:doi": "10.5555/SC.1",
        "link": [{"@ref": "scopus", "@href": "https://www.scopus.com/record/1"}],
        "subtypeDescription": "Article", "eid": "2-s2.0-1", "citedby-count": "3"}]}},
    "api.elsevier.com/content/search/sciencedirect": {"search-results": {"opensearch:totalResults": "1", "entry": [{
        "dc:title": "Inflation under drought", "prism:coverDate": "2021-06-01",
        "authors": {"author": [{"$": "Maria Silva"}, {"$": "João Costa"}]},
        "prism:publicationName": "Journal of Macroeconomics", "prism:doi": "10.5555/SD.1",
        "link": [{"@ref": "scidir", "@href": "https://www.sciencedirect.com/science/article/pii/1"}],
        "prism:startingPage": "5", "prism:endingPage": "9", "pii": "1", "openaccess": "true"}]}},
    "api.clarivate.com": {"metadata": {"total": 1}, "hits": [{
        "uid": "WOS:0001", "title": "Threshold Phillips curves", "types": ["Article"],
        "source": {"sourceTitle": "ECONOMIC MODELLING", "publishYear": 2026, "volume": "3", "issue": "1",
                   "pages": {"range": "1-10"}},
        "names": {"authors": [{"displayName": "Doe, Jane"}]}, "identifiers": {"doi": "10.5555/WS.1"},
        "links": {"record": "https://www.webofscience.com/wos/woscc/full-record/WOS:0001"}}]},
    "serpapi.com": {"search_information": {"total_results": 1}, "organic_results": [{
        "title": "Inflation and war", "link": "https://example.org/gs", "snippet": "War raises inflation.",
        "publication_info": {"summary": "J Doe, A Roe - Journal of Peace Economics, 2023 - example.org"},
        "inline_links": {"cited_by": {"total": 5}}}]},
}


class FakeApi:
    def __init__(self, status=None):
        self.calls, self.status = [], status or {}

    def __call__(self, url, headers, timeout=30.0):
        self.calls.append((url, dict(headers)))
        parts = urllib.parse.urlsplit(url)
        for key in sorted(PAYLOADS, key=len, reverse=True):
            host, _, path = key.partition("/")
            if parts.netloc == host and parts.path.startswith("/" + path):
                if self.status.get(key):
                    return self.status[key].pop(0)
                body = PAYLOADS[key]
                return 200, (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        return 404, b"not found"


@pytest.fixture
def keys(monkeypatch):
    for k, v in {"ELSEVIER_API_KEY": "els-secret", "WOS_API_KEY": "wos-secret", "SERPAPI_API_KEY": "serp-secret",
                 "CONTACT_EMAIL": "me@uni.edu", "S2_API_KEY": "s2-secret"}.items():
        monkeypatch.setenv(k, v)


def test_all_adapters_save_records_and_log(folder, keys, capsys):
    (folder / FILES["protocol"]).write_text("Literature window: 2021-2026\n", encoding="utf-8")
    api = FakeApi()
    code = ss.main([str(folder), "--query", Q, "--sources", ",".join(ss.SOURCES), "--max", "5"],
                   transport=api, sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0, out
    for secret in ("els-secret", "wos-secret", "serp-secret", "s2-secret"):
        assert secret not in out
    rows = {}
    for label in ("OpenAlex", "Crossref", "SemanticScholar", "arXiv", "Scopus", "ScienceDirect", "WebOfScience",
                  "GoogleScholar-SerpApi"):
        part = read_csv(folder / f"03_records_part-{label}.csv")
        assert len(part) == 1, label
        rows[label] = part[0]
    assert rows["OpenAlex"]["authors"] == "van der Berg, Jane; Kaya, Ali"
    assert rows["OpenAlex"]["doi"] == "10.5555/oa.1" and rows["OpenAlex"]["pages"] == "1-20"
    assert rows["OpenAlex"]["abstract"] == "Oil matters" and "oa_url=" in rows["OpenAlex"]["notes"]
    assert rows["Crossref"]["authors"] == "Demir, Ayşe" and rows["Crossref"]["abstract"] == "Tagged abstract."
    assert rows["SemanticScholar"]["venue"] == "J. Intl. Econ." and rows["SemanticScholar"]["type"] == "journal-article"
    assert rows["arXiv"]["title"] == "Regime-dependent inflation persistence"
    assert rows["arXiv"]["authors"] == "Lopez, Ana; Chen, Wei" and rows["arXiv"]["year"] == "2024"
    assert rows["Scopus"]["year"] == "2025" and "first author only" in rows["Scopus"]["notes"]
    assert rows["ScienceDirect"]["authors"] == "Silva, Maria; Costa, João" and rows["ScienceDirect"]["pages"] == "5-9"
    assert rows["WebOfScience"]["doi"] == "10.5555/ws.1" and rows["WebOfScience"]["year"] == "2026"
    assert rows["GoogleScholar-SerpApi"]["authors"] == "Doe, J; Roe, A"
    assert rows["GoogleScholar-SerpApi"]["venue"] == "Journal of Peace Economics"
    assert rows["OpenAlex"]["record_id"] == "OA-Q01-0001" and rows["OpenAlex"]["query_id"] == "Q01-OA"
    log = read_csv(folder / FILES["search_log"])
    assert len(log) == 8 and all(r["filters"] == "publication years 2021-2026" for r in log)
    urls = {urllib.parse.urlsplit(u).netloc: (u, h) for u, h in api.calls}
    assert "from_publication_date%3A2021-01-01" in urls["api.openalex.org"][0]
    assert "year=2021-2026" in urls["api.semanticscholar.org"][0]
    assert urls["api.semanticscholar.org"][1]["x-api-key"] == "s2-secret"
    assert urls["api.elsevier.com"][1]["X-ELS-APIKey"] == "els-secret"
    assert urls["api.clarivate.com"][1]["X-ApiKey"] == "wos-secret"
    assert "PY%3D%282021-2026%29" in urls["api.clarivate.com"][0]
    assert "as_ylo=2021" in urls["serpapi.com"][0]
    assert "mailto=me%40uni.edu" in urls["api.crossref.org"][0]


def test_missing_keys_are_reported_not_fatal(folder, monkeypatch, capsys):
    for k in ("ELSEVIER_API_KEY", "WOS_API_KEY", "SERPAPI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    code = ss.main([str(folder), "--query", "x", "--sources", "openalex,scopus,wos", "--window", "2021-2026"],
                   transport=FakeApi(), sleep=lambda s: None)
    out = capsys.readouterr().out
    assert code == 0 and "Scopus: HTTP 401" in out and "WebOfScience: HTTP 401" in out
    assert (folder / "03_records_part-OpenAlex.csv").exists()


def test_retry_on_429_then_success():
    api = FakeApi(status={"api.openalex.org": [(429, b"slow down")]})
    waits = []
    http = ss.Http(api, sleep=waits.append)
    data = http.json("https://api.openalex.org/works?search=x")
    assert waits == [2] and len(api.calls) == 2 and data["meta"]["count"] == 1
    api = FakeApi(status={"api.openalex.org": [(403, b"forbidden")]})
    with pytest.raises(ss.ApiError) as err:
        ss.Http(api, sleep=waits.append).json("https://api.openalex.org/works?search=x")
    assert err.value.status == 403 and len(api.calls) == 1


def test_blocked_network_exits_2_and_dry_run_prints_urls(folder, capsys):
    def blocked(url, headers, timeout=30.0):
        raise ss.NetworkBlocked("proxy refused")
    assert ss.main([str(folder), "--query", "x", "--sources", "openalex,crossref"], transport=blocked,
                   sleep=lambda s: None) == 2
    capsys.readouterr()
    assert ss.main([str(folder), "--query", "x", "--sources", "openalex,scholar", "--dry-run"],
                   transport=blocked, sleep=lambda s: None) == 0
    out = capsys.readouterr().out
    assert "https://api.openalex.org/works?search=x" in out and "api_key=<KEY>" in out


def test_print_queries_needs_no_folder(capsys):
    assert ss.main(["--print-queries", "--query", Q, "--window", "2020-2026"]) == 0
    out = capsys.readouterr().out
    assert "Web of Science (Advanced Search)" in out and "PY=(2020-2026)" in out


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
WOS_TXT = """FN Clarivate Analytics Web of Science
VR 1.0
PT J
AU Doe, J
   Kaya, A
AF Doe, Jane
   Kaya, Ali
TI Regime switching in the hybrid
   Phillips curve
SO JOURNAL OF MACROECONOMICS
PY 2023
VL 75
BP 10
EP 25
DI 10.5555/WOS.2
UT WOS:000123
ER

PT J
AF Old, Olga
TI A pre-window classic
SO ECONOMIC JOURNAL
PY 2012
ER

EF
"""

RIS = """TY  - JOUR
AU  - Silva, Maria
AU  - Costa, João
TI  - Climate shocks and inflation
T2  - Energy Economics
PY  - 2024
VL  - 130
SP  - 1
EP  - 12
DO  - https://doi.org/10.5555/RIS.1
ER  -
"""

BIB = """@article{key1,
  title = {Geopolitical {Risk} and Prices},
  author = {Caldara, Dario and Iacoviello, Matteo},
  journal = {American Economic Review},
  year = {2022},
  volume = {112}, number = {4}, pages = {1194--1225},
  doi = {10.5555/BIB.1}
}"""

SCOPUS_CSV = ('Authors,Author full names,Title,Year,Source title,Volume,Issue,Page start,Page end,DOI,'
              'Document Type,EID,Cited by\n'
              '"Demir A.; Yilmaz B.","Demir, Ayşe (57000000001); Yılmaz, Burak (57000000002)",'
              'Exchange rate pass-through,2021,Emerging Markets Review,40,,1,15,10.5555/SC.2,Article,2-s2.0-2,7\n')

POP_CSV = ("Cites,Authors,Title,Year,Source,Publisher,ArticleURL,GSRank,DOI,Type\n"
           '12,"J Doe, A Roe",Inflation and war,2023,Peace Econ,X,https://example.org/a,1,,Article\n')


def test_detect_and_parse_formats(tmp_path):
    files = {"wos.txt": WOS_TXT, "x.ris": RIS, "x.bib": BIB, "scopus.csv": SCOPUS_CSV, "pop.csv": POP_CSV}
    got = {}
    for name, text in files.items():
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        fmt, rows = import_records.parse_file(p)
        got[fmt] = rows
    assert set(got) == {"wos_plain", "ris", "bibtex", "scopus", "pop"}
    w = got["wos_plain"][0]
    assert w["authors"] == "Doe, Jane; Kaya, Ali" and w["title"] == "Regime switching in the hybrid Phillips curve"
    assert w["pages"] == "10-25" and w["doi"] == "10.5555/wos.2" and "WOS:000123" in w["notes"]
    assert got["ris"][0]["authors"] == "Silva, Maria; Costa, João" and got["ris"][0]["doi"] == "10.5555/ris.1"
    assert got["bibtex"][0]["title"] == "Geopolitical Risk and Prices" and got["bibtex"][0]["pages"] == "1194-1225"
    assert got["scopus"][0]["authors"] == "Demir, Ayşe; Yılmaz, Burak" and "eid=2-s2.0-2" in got["scopus"][0]["notes"]
    assert got["pop"][0]["authors"] == "Doe, J; Roe, A"


def test_json_leads_from_connectors(tmp_path):
    scispace = {"papers": [{"title": "Do Geopolitical Risks Raise or Lower Inflation?", "date": "2024-01-01T00:00:00Z",
                            "doi": "10.5555/GPR.1", "authors": {"total": 2, "data": [{"display_name": "Matteo Iacoviello"},
                                                                                    {"display_name": "Dario Caldara"}]},
                            "journal": None, "metrics": {"citations": {"total": 34}}},
                           {"title": "Old paper", "date": "2017-01-01", "doi": None, "authors": {"data": []},
                            "paper_urls": {"data": {"Html": ["https://ideas.repec.org/p/x.html"]}}}]}
    leads = [{"title": "A lead", "authors": ["S. Yildirim", "A. Other"], "year": 2026, "venue": "Applied Economics",
              "url": "https://consensus.app/papers/details/abc/"},
             {"title": "Second lead", "authors": "Ihlas Sovbetov", "year": "2025", "doi": "https://doi.org/10.5555/L.2"}]
    (tmp_path / "s.json").write_text(json.dumps(scispace), encoding="utf-8")
    (tmp_path / "c.jsonl").write_text("\n".join(json.dumps(x) for x in leads), encoding="utf-8")
    fmt, rows = import_records.parse_file(tmp_path / "s.json")
    assert fmt == "json" and rows[0]["authors"] == "Iacoviello, Matteo; Caldara, Dario"
    assert rows[0]["year"] == "2024" and rows[0]["doi"] == "10.5555/gpr.1" and "cited_by=34" in rows[0]["notes"]
    assert rows[1]["url"] == "https://ideas.repec.org/p/x.html" and rows[1]["year"] == "2017"
    fmt, rows = import_records.parse_file(tmp_path / "c.jsonl")
    assert [r["authors"] for r in rows] == ["Yildirim, S.; Other, A.", "Sovbetov, Ihlas"]
    assert rows[1]["doi"] == "10.5555/l.2" and all("verify" in r["notes"] for r in rows)


def test_import_cli_writes_parts_logs_and_flags_window(folder, tmp_path):
    (tmp_path / "savedrecs.txt").write_text(WOS_TXT, encoding="utf-8")
    (tmp_path / "x.ris").write_text(RIS, encoding="utf-8")
    code, out = run("import_records.py", folder, tmp_path / "savedrecs.txt", "--window", "2021-2026",
                    "--query", "TS=(phillips) AND PY=(2021-2026)")
    assert code == 0 and "1 outside the window" in out
    code, out = run("import_records.py", folder, tmp_path / "x.ris", "--source", "ScienceDirect")
    assert code == 0
    wos = read_csv(folder / "03_records_part-WebOfScience.csv")
    assert [r["record_id"] for r in wos] == ["WS-00001", "WS-00002"]
    sd = read_csv(folder / "03_records_part-Sciencedirect.csv")
    assert sd[0]["record_id"] == "SD-00001" and sd[0]["source"] == "ScienceDirect"
    log = read_csv(folder / FILES["search_log"])
    assert [r["query_id"] for r in log] == ["I01-WS", "I02-SD"]
    assert log[0]["query_string"].startswith("TS=(phillips)")
    code, out = run("dedupe_records.py", folder)
    assert code == 0 and len(read_csv(folder / FILES["records_dedup"])) == 3


def test_prefixes():
    assert import_records.prefix_for("Consensus") == "CN"
    assert import_records.prefix_for("SciSpace") == "SS"
    assert import_records.prefix_for("Scopus") == "SC"
    assert import_records.prefix_for("CORE") == "CO"
    assert import_records.prefix_for("Some Index") == "SO"


# ---------------------------------------------------------------------------
# Open-access full texts
# ---------------------------------------------------------------------------
def test_find_fulltext_chain(folder, monkeypatch, capsys):
    monkeypatch.setenv("UNPAYWALL_EMAIL", "me@uni.edu")
    ver = [{"ref_id": "A", "status": "VERIFIED", "doi": "10.5555/a"},
           {"ref_id": "B", "status": "VERIFIED", "doi": "10.5555/b"},
           {"ref_id": "C", "status": "PREPRINT", "doi": "10.5555/c"},
           {"ref_id": "D", "status": "VERIFIED", "doi": ""},
           {"ref_id": "E", "status": "NOT_VERIFIED", "doi": "10.5555/e"}]
    write(folder, "verification", ver)

    def api(url, headers, timeout=30.0):
        if "unpaywall" in url:
            if "10.5555/a" in url:
                return 200, json.dumps({"is_oa": True, "best_oa_location": {
                    "url_for_pdf": "https://repo.org/a.pdf", "host_type": "repository", "version": "acceptedVersion",
                    "license": "cc-by"}}).encode()
            return 200, json.dumps({"is_oa": False}).encode()
        if "openalex" in url:
            if "10.5555/b" in url:
                return 200, json.dumps({"open_access": {"is_oa": True, "oa_url": "https://pub.org/b"},
                                        "best_oa_location": {"landing_page_url": "https://pub.org/b"}}).encode()
            return 404, b"{}"
        if "semanticscholar" in url:
            return 200, json.dumps({"openAccessPdf": None, "externalIds": {"ArXiv": "2401.00001"}}).encode()
        return 404, b""

    assert find_fulltext.main([str(folder)], transport=api) == 0
    rows = {r["ref_id"]: r for r in read_csv(folder / FILES["fulltext"])}
    assert rows["A"]["oa_url"] == "https://repo.org/a.pdf" and rows["A"]["version"] == "acceptedVersion"
    assert rows["B"]["oa_source"] == "OpenAlex"
    assert rows["C"]["oa_url"] == "https://arxiv.org/abs/2401.00001"
    assert "no DOI" in rows["D"]["notes"] and "E" not in rows
    capsys.readouterr()
    assert find_fulltext.main([str(folder), "--dry-run"], transport=api) == 0
    out = capsys.readouterr().out
    assert "https://api.unpaywall.org/v2/10.5555/a?email=me@uni.edu" in out
