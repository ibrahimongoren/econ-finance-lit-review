#!/usr/bin/env python3
"""Search scholarly databases over the review's publication window and save normalized records.

Usage:
    python3 scripts/search_sources.py litrev-<slug>/ --query '"phillips curve" AND (geopolitical OR climate)' \
        --sources openalex,crossref,semanticscholar,arxiv,scopus,sciencedirect,wos,scholar \
        [--window 2021-2026] [--max 300] [--query-id Q01] [--q-scopus '...'] [--dry-run] [--env-file .env]
    python3 scripts/search_sources.py --print-queries --query '...' [--window 2021-2026]

--query takes one Boolean string (AND / OR / NOT in capitals, "quoted phrases", parentheses).
It is translated into each database's own syntax; --q-<source> overrides the translation for one
source. --print-queries shows the translated strings - paste them into the Web of Science, Scopus,
ScienceDirect or Google Scholar web interfaces when you export results by hand (then run
import_records.py). The window defaults to the "Literature window" line of 00_protocol.md, else the
last five years.

Sources and access (keys come from the environment or an optional .env file; they are never printed):
  openalex        free. OPENALEX_API_KEY optional (search is metered; a free key raises the budget).
                  Basic paging is used (page x per_page <= 10,000; per_page max 100).
  crossref        free. CONTACT_EMAIL recommended (sent in the User-Agent). Relevance-ranked: totals are
                  huge, so --max caps retrieval; screen carefully.
  semanticscholar free bulk search. S2_API_KEY optional (higher rate limit).
  arxiv           free. 3-second pause between calls, as the arXiv API manual asks.
  scopus          ELSEVIER_API_KEY and an institutional subscription to the Scopus API (campus network,
                  VPN or ELSEVIER_INSTTOKEN). STANDARD view returns the first author only.
  sciencedirect   ELSEVIER_API_KEY and an institutional ScienceDirect API subscription.
  wos             WOS_API_KEY for the Web of Science Starter API (free trial plan: 1 request/s, 50/day).
  scholar         SERPAPI_API_KEY (Google Scholar through SerpApi, a paid service; Google Scholar itself
                  offers no API). Results carry no DOI - treat them as leads for verification.

Writes 03_records_part-<SOURCE>.csv (dedupe_records.py merges them) and appends one row per source to
02_search_log.csv with query_id <query-id>-<PREFIX>. Exit code 2 when the network is blocked: use
--dry-run, which prints the request URLs for the web fetch tool, or research connectors and exports.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, load_env, norm_doi, parse_window,  # noqa: E402
                           read_csv, reconstruct_abstract, strip_markup, to_int, window_from_protocol,
                           write_csv)

UA = "econ-finance-lit-review/2.0 (literature review; mailto:{email})"
SOURCES = {
    #  key              prefix  label               pause (s)
    "openalex":        ("OA", "OpenAlex", 0.2),
    "crossref":        ("CR", "Crossref", 1.0),
    "semanticscholar": ("S2", "SemanticScholar", 1.1),
    "arxiv":           ("AX", "arXiv", 3.0),
    "scopus":          ("SC", "Scopus", 0.5),
    "sciencedirect":   ("SD", "ScienceDirect", 0.6),
    "wos":             ("WS", "WebOfScience", 1.1),
    "scholar":         ("GS", "GoogleScholar-SerpApi", 1.0),
}
PARTICLES = {"de", "da", "del", "der", "di", "du", "van", "von", "le", "la", "dos", "das", "ter", "ten", "bin", "al"}


class NetworkBlocked(RuntimeError):
    """The host cannot be reached at all (proxy or sandbox), as opposed to an API error."""


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


# ---------------------------------------------------------------------------
# HTTP layer (injectable for tests)
# ---------------------------------------------------------------------------
def urllib_transport(url: str, headers: dict, timeout: float = 30.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise NetworkBlocked(f"{urllib.parse.urlsplit(url).netloc}: {e}") from e


class Http:
    def __init__(self, transport=urllib_transport, email: str = "", sleep=time.sleep):
        self.transport = transport
        self.email = email or "anonymous@example.org"
        self.sleep = sleep
        self.calls = 0

    def get(self, url: str, headers: dict | None = None, tries: int = 4) -> bytes:
        h = {"User-Agent": UA.format(email=self.email), "Accept": "application/json"}
        h.update(headers or {})
        for attempt in range(tries):
            status, body = self.transport(url, h)
            self.calls += 1
            if status == 200:
                return body
            if status in (429, 500, 502, 503, 504) and attempt < tries - 1:
                self.sleep(2 ** (attempt + 1))
                continue
            text = body[:300].decode("utf-8", "replace") if body else ""
            raise ApiError(status, text)
        raise ApiError(599, "retries exhausted")

    def json(self, url: str, headers: dict | None = None) -> dict:
        return json.loads(self.get(url, headers).decode("utf-8"))


# ---------------------------------------------------------------------------
# Query translation
# ---------------------------------------------------------------------------
TOKEN = re.compile(r'"[^"]*"|\(|\)|[^\s()"]+')


def tokens(q: str) -> list[str]:
    return TOKEN.findall(q or "")


def to_openalex(q: str) -> str:
    return " ".join(tokens(q))


def to_s2(q: str) -> str:
    """Semantic Scholar bulk syntax: + AND, | OR, - NOT, quotes for phrases."""
    out, toks = [], tokens(q)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == "AND" and i + 1 < len(toks) and toks[i + 1] == "NOT":
            out.append("-")
            i += 2
            continue
        out.append({"AND": "+", "OR": "|", "NOT": "-"}.get(t, t))
        i += 1
    s = " ".join(out)
    return re.sub(r"-\s+", "-", s)


def _not_to_and_not(q: str) -> str:
    toks, out = tokens(q), []
    for i, t in enumerate(toks):
        if t == "NOT" and (i == 0 or toks[i - 1] != "AND"):
            out += ["AND", "NOT"] if out else ["NOT"]
        else:
            out.append(t)
    return " ".join(out)


def to_scopus(q: str) -> str:
    return f"TITLE-ABS-KEY({_not_to_and_not(q)})"


def to_sciencedirect(q: str) -> str:
    return _not_to_and_not(q)


def to_wos(q: str, window: tuple[int, int]) -> str:
    return f"TS=({' '.join(tokens(q))}) AND PY=({window[0]}-{window[1]})"


def to_crossref(q: str) -> str:
    """Crossref's query.bibliographic has no Boolean logic: keep the words, drop operators and NOT-terms."""
    out, skip = [], False
    for t in tokens(q):
        if t == "NOT":
            skip = True
            continue
        if t in ("AND", "OR", "(", ")"):
            continue
        if skip:
            skip = False
            continue
        out.append(t.strip('"'))
    return " ".join(out)


def to_arxiv(q: str) -> str:
    out = []
    for t in tokens(q):
        if t in ("AND", "OR", "(", ")"):
            out.append(t)
        elif t == "NOT":
            if out and out[-1] == "AND":
                out[-1] = "ANDNOT"
            else:
                out.append("ANDNOT")
        else:
            out.append(f"all:{t}")
    # implicit AND between adjacent terms
    fixed = []
    for t in out:
        if fixed and t.startswith("all:") and (fixed[-1].startswith("all:") or fixed[-1] == ")"):
            fixed.append("AND")
        fixed.append(t)
    return " ".join(fixed)


def to_scholar(q: str) -> str:
    out, neg = [], False
    for t in tokens(q):
        if t == "AND":
            continue
        if t == "NOT":
            neg = True
            continue
        out.append(("-" + t) if neg else t)
        neg = False
    return " ".join(out).replace("( ", "(").replace(" )", ")")


def translate(source: str, q: str, window: tuple[int, int]) -> str:
    return {
        "openalex": to_openalex, "crossref": to_crossref, "semanticscholar": to_s2, "arxiv": to_arxiv,
        "scopus": to_scopus, "sciencedirect": to_sciencedirect, "scholar": to_scholar,
    }.get(source, lambda x: x)(q) if source != "wos" else to_wos(q, window)


def web_interface_queries(q: str, window: tuple[int, int]) -> dict:
    """Strings for manual searches and exports in each database's own web interface."""
    y0, y1 = window
    return {
        "Web of Science (Advanced Search)": to_wos(q, window),
        "Scopus (Advanced document search)": f"{to_scopus(q)} AND PUBYEAR > {y0 - 1} AND PUBYEAR < {y1 + 1}",
        "ScienceDirect (Advanced search: terms + Years)": f"{to_sciencedirect(q)}   [Years: {y0}-{y1}]",
        "Google Scholar / Publish or Perish": f"{to_scholar(q)}   [Years: {y0}-{y1}]",
        "Semantic Scholar (bulk API syntax)": to_s2(q),
        "OpenAlex": to_openalex(q),
        "arXiv": to_arxiv(q),
        "Crossref (keywords)": to_crossref(q),
    }


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
def family_first(name: str) -> str:
    """'Jane van der Berg' -> 'van der Berg, Jane'; names already 'Family, Given' are kept."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name or "," in name:
        return name
    parts = name.split(" ")
    if len(parts) == 1:
        return name
    i = len(parts) - 1
    while i - 1 > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return f"{' '.join(parts[i:])}, {' '.join(parts[:i])}"


def record(**kw) -> dict:
    row = {k: "" for k in HEADERS[FILES["records"]]}
    row.update({k: ("" if v is None else str(v)) for k, v in kw.items() if k in row})
    return row


def note_join(*parts) -> str:
    return "; ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Source adapters: each returns (total_hits, records, notes)
# ---------------------------------------------------------------------------
def search_openalex(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    base = "https://api.openalex.org/works"
    per = min(100, max_n)
    params = {"search": q, "filter": f"from_publication_date:{window[0]}-01-01,to_publication_date:{window[1]}-12-31",
              "per_page": per}
    if env.get("OPENALEX_API_KEY"):
        params["api_key"] = env["OPENALEX_API_KEY"]
    out, total, page = [], 0, 1
    while len(out) < max_n and page * per <= 10_000:
        url = f"{base}?{urllib.parse.urlencode(dict(params, page=page))}"
        if dry:
            return 0, [], [redact(url)]
        data = http.json(url)
        total = data.get("meta", {}).get("count", total)
        results = data.get("results", [])
        for w in results:
            src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
            b = w.get("biblio") or {}
            pages = "-".join(x for x in (b.get("first_page"), b.get("last_page")) if x)
            out.append(record(
                title=w.get("display_name") or w.get("title"), year=w.get("publication_year"),
                authors="; ".join(family_first((a.get("author") or {}).get("display_name", ""))
                                  for a in w.get("authorships") or []),
                venue=src, volume=b.get("volume"), issue=b.get("issue"), pages=pages,
                doi=norm_doi(w.get("doi") or ""), url=w.get("id"), type=w.get("type"),
                language=w.get("language"), abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
                notes=note_join(f"cited_by={w.get('cited_by_count')}" if w.get("cited_by_count") is not None else "",
                                f"oa_url={(w.get('open_access') or {}).get('oa_url')}"
                                if (w.get("open_access") or {}).get("oa_url") else "")))
        if len(results) < per:
            break
        page += 1
        http.sleep(SOURCES["openalex"][2])
    return total, out[:max_n], []


def search_crossref(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    base = "https://api.crossref.org/works"
    rows = min(100, max_n)
    params = {"query.bibliographic": q, "filter": f"from-pub-date:{window[0]}-01-01,until-pub-date:{window[1]}-12-31",
              "rows": rows, "select": "DOI,title,author,issued,container-title,type,volume,issue,page,abstract,URL,language"}
    if env.get("CONTACT_EMAIL"):
        params["mailto"] = env["CONTACT_EMAIL"]
    out, total, cursor = [], 0, "*"
    while len(out) < max_n and cursor:
        url = f"{base}?{urllib.parse.urlencode(dict(params, cursor=cursor))}"
        if dry:
            return 0, [], [redact(url)]
        msg = http.json(url).get("message", {})
        total = msg.get("total-results", total)
        items = msg.get("items", [])
        for it in items:
            year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
            authors = "; ".join(f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") if a.get("family")
                                else a.get("name", "") for a in it.get("author") or [])
            out.append(record(
                title=(it.get("title") or [""])[0], year=year, authors=authors,
                venue=(it.get("container-title") or [""])[0], volume=it.get("volume"), issue=it.get("issue"),
                pages=it.get("page"), doi=norm_doi(it.get("DOI", "")), url=it.get("URL"), type=it.get("type"),
                language=it.get("language"), abstract=strip_markup(it.get("abstract", ""))))
        cursor = msg.get("next-cursor") if items else None
        if len(items) < rows:
            break
        http.sleep(SOURCES["crossref"][2])
    notes = ["Crossref ranks by relevance over the whole registry; totals are not topic counts"] if total else []
    return total, out[:max_n], notes


def search_semanticscholar(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    base = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    params = {"query": q, "year": f"{window[0]}-{window[1]}",
              "fields": "title,year,venue,authors,externalIds,abstract,url,citationCount,openAccessPdf,"
                        "publicationTypes,journal"}
    headers = {"x-api-key": env["S2_API_KEY"]} if env.get("S2_API_KEY") else {}
    out, total, token = [], 0, None
    while len(out) < max_n:
        url = f"{base}?{urllib.parse.urlencode(dict(params, **({'token': token} if token else {})))}"
        if dry:
            return 0, [], [redact(url)]
        data = http.json(url, headers)
        total = data.get("total", total)
        for p in data.get("data") or []:
            ext = p.get("externalIds") or {}
            journal = p.get("journal") or {}
            types = p.get("publicationTypes") or []
            pdf = (p.get("openAccessPdf") or {}).get("url")
            out.append(record(
                title=p.get("title"), year=p.get("year"),
                authors="; ".join(family_first(a.get("name", "")) for a in p.get("authors") or []),
                venue=journal.get("name") or p.get("venue"), volume=journal.get("volume"),
                pages=(journal.get("pages") or "").strip(), doi=norm_doi(ext.get("DOI", "")), url=p.get("url"),
                type="journal-article" if "JournalArticle" in types else (types[0] if types else ""),
                abstract=p.get("abstract"),
                notes=note_join(f"cited_by={p.get('citationCount')}" if p.get("citationCount") is not None else "",
                                f"oa_url={pdf}" if pdf else "",
                                f"arxiv={ext['ArXiv']}" if ext.get("ArXiv") else "")))
        token = data.get("token")
        if not token or not data.get("data"):
            break
        http.sleep(SOURCES["semanticscholar"][2])
    return total, out[:max_n], []


ATOM = {"a": "http://www.w3.org/2005/Atom", "os": "http://a9.com/-/spec/opensearch/1.1/",
        "ax": "http://arxiv.org/schemas/atom"}


def search_arxiv(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    base = "https://export.arxiv.org/api/query"
    sq = f"({q}) AND submittedDate:[{window[0]}01010000 TO {window[1]}12312359]"
    out, total, start, per = [], 0, 0, min(100, max_n)
    while len(out) < max_n:
        url = f"{base}?search_query={urllib.parse.quote_plus(sq, safe=':[]')}&start={start}&max_results={per}"
        if dry:
            return 0, [], [url]
        root = ET.fromstring(http.get(url, {"Accept": "application/atom+xml"}))
        t = root.find("os:totalResults", ATOM)
        total = int(t.text) if t is not None and t.text else total
        entries = root.findall("a:entry", ATOM)
        for e in entries:
            def txt(path):
                el = e.find(path, ATOM)
                return re.sub(r"\s+", " ", el.text).strip() if el is not None and el.text else ""
            link = next((ln.get("href") for ln in e.findall("a:link", ATOM) if ln.get("rel") == "alternate"),
                        txt("a:id"))
            out.append(record(
                title=txt("a:title"), year=txt("a:published")[:4],
                authors="; ".join(family_first(a.findtext("a:name", "", ATOM)) for a in e.findall("a:author", ATOM)),
                venue=txt("ax:journal_ref") or "arXiv", doi=norm_doi(txt("ax:doi")), url=link,
                type="preprint", abstract=txt("a:summary"), notes=f"arxiv_id={txt('a:id').rsplit('/', 1)[-1]}"))
        if len(entries) < per:
            break
        start += per
        http.sleep(SOURCES["arxiv"][2])
    return total, out[:max_n], []


def _elsevier_headers(env: dict) -> dict:
    h = {"X-ELS-APIKey": env.get("ELSEVIER_API_KEY", ""), "Accept": "application/json"}
    if env.get("ELSEVIER_INSTTOKEN"):
        h["X-ELS-Insttoken"] = env["ELSEVIER_INSTTOKEN"]
    return h


def _els_entries(data: dict) -> tuple[int, list]:
    sr = data.get("search-results", {})
    total = int(sr.get("opensearch:totalResults") or 0)
    entries = [e for e in sr.get("entry", []) if "error" not in e]
    return total, entries


def search_scopus(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    if not env.get("ELSEVIER_API_KEY") and not dry:
        raise ApiError(401, "ELSEVIER_API_KEY not set")
    base = "https://api.elsevier.com/content/search/scopus"
    out, total, start, per = [], 0, 0, 25
    while len(out) < max_n and start < 5000:
        url = f"{base}?{urllib.parse.urlencode({'query': q, 'date': f'{window[0]}-{window[1]}', 'count': per, 'start': start, 'view': 'STANDARD'})}"
        if dry:
            return 0, [], [url + "  [headers: X-ELS-APIKey, optional X-ELS-Insttoken]"]
        total, entries = _els_entries(http.json(url, _elsevier_headers(env)))
        for e in entries:
            scopus_link = next((ln.get("@href") for ln in e.get("link", []) if ln.get("@ref") == "scopus"), "")
            out.append(record(
                title=e.get("dc:title"), year=(e.get("prism:coverDate") or "")[:4], authors=e.get("dc:creator", ""),
                venue=e.get("prism:publicationName"), volume=e.get("prism:volume"),
                issue=e.get("prism:issueIdentifier"), pages=e.get("prism:pageRange"),
                doi=norm_doi(e.get("prism:doi", "")), url=scopus_link,
                type="journal-article" if e.get("subtypeDescription") == "Article" else e.get("subtypeDescription"),
                notes=note_join(f"eid={e.get('eid')}" if e.get("eid") else "",
                                f"cited_by={e.get('citedby-count')}" if e.get("citedby-count") else "",
                                "authors=first author only (Scopus STANDARD view)")))
        if len(entries) < per:
            break
        start += per
        http.sleep(SOURCES["scopus"][2])
    return total, out[:max_n], []


def search_sciencedirect(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    if not env.get("ELSEVIER_API_KEY") and not dry:
        raise ApiError(401, "ELSEVIER_API_KEY not set")
    base = "https://api.elsevier.com/content/search/sciencedirect"
    out, total, start, per = [], 0, 0, 100
    while len(out) < max_n and start <= 6000:
        url = f"{base}?{urllib.parse.urlencode({'query': q, 'date': f'{window[0]}-{window[1]}', 'count': per, 'start': start})}"
        if dry:
            return 0, [], [url + "  [headers: X-ELS-APIKey, optional X-ELS-Insttoken]"]
        total, entries = _els_entries(http.json(url, _elsevier_headers(env)))
        for e in entries:
            auths = (e.get("authors") or {}).get("author", [])
            if isinstance(auths, dict):
                auths = [auths]
            names = [a.get("$", "") for a in auths] if isinstance(auths, list) else [str(auths)]
            link = next((ln.get("@href") for ln in e.get("link", []) if ln.get("@ref") == "scidir"), "")
            pages = "-".join(x for x in (e.get("prism:startingPage"), e.get("prism:endingPage")) if x)
            out.append(record(
                title=e.get("dc:title"), year=(e.get("prism:coverDate") or "")[:4],
                authors="; ".join(family_first(n) for n in names) or e.get("dc:creator", ""),
                venue=e.get("prism:publicationName"), volume=e.get("prism:volume"), pages=pages,
                doi=norm_doi(e.get("prism:doi", "")), url=link, type="journal-article",
                notes=note_join(f"pii={e.get('pii')}" if e.get("pii") else "",
                                "open access" if str(e.get("openaccess")).lower() in ("true", "1") else "")))
        if len(entries) < per:
            break
        start += per
        http.sleep(SOURCES["sciencedirect"][2])
    return total, out[:max_n], []


def search_wos(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    if not env.get("WOS_API_KEY") and not dry:
        raise ApiError(401, "WOS_API_KEY not set")
    base = "https://api.clarivate.com/apis/wos-starter/v1/documents"
    db = env.get("WOS_DB", "WOS")
    out, total, page, per = [], 0, 1, 50
    while len(out) < max_n:
        url = f"{base}?{urllib.parse.urlencode({'db': db, 'q': q, 'limit': per, 'page': page})}"
        if dry:
            return 0, [], [url + "  [header: X-ApiKey]"]
        data = http.json(url, {"X-ApiKey": env.get("WOS_API_KEY", "")})
        total = (data.get("metadata") or {}).get("total", total)
        hits = data.get("hits") or []
        for h in hits:
            src = h.get("source") or {}
            names = (h.get("names") or {}).get("authors") or []
            out.append(record(
                title=h.get("title"), year=src.get("publishYear"),
                authors="; ".join(a.get("displayName") or a.get("wosStandard") or "" for a in names),
                venue=src.get("sourceTitle"), volume=src.get("volume"), issue=src.get("issue"),
                pages=(src.get("pages") or {}).get("range"), doi=norm_doi((h.get("identifiers") or {}).get("doi", "")),
                url=(h.get("links") or {}).get("record"),
                type="journal-article" if "Article" in (h.get("types") or []) else ", ".join(h.get("types") or []),
                notes=f"wos_uid={h.get('uid')}"))
        if len(hits) < per:
            break
        page += 1
        http.sleep(SOURCES["wos"][2])
    return total, out[:max_n], []


def search_scholar(http: Http, q: str, window, max_n: int, env: dict, dry: bool = False):
    if not env.get("SERPAPI_API_KEY") and not dry:
        raise ApiError(401, "SERPAPI_API_KEY not set")
    base = "https://serpapi.com/search.json"
    out, total, start, per = [], 0, 0, 20
    while len(out) < max_n:
        params = {"engine": "google_scholar", "q": q, "as_ylo": window[0], "as_yhi": window[1], "num": per,
                  "start": start, "api_key": env.get("SERPAPI_API_KEY", "KEY")}
        url = f"{base}?{urllib.parse.urlencode(params)}"
        if dry:
            return 0, [], [redact(url)]
        data = http.json(url)
        total = (data.get("search_information") or {}).get("total_results", total)
        results = data.get("organic_results") or []
        for r in results:
            summary = (r.get("publication_info") or {}).get("summary", "")
            authors_part = summary.split(" - ")[0] if " - " in summary else ""
            year = to_int(summary)
            out.append(record(
                title=r.get("title"), year=year or "",
                authors="; ".join(family_first(a.strip()) for a in authors_part.split(",")
                                  if a.strip() and "…" not in a),
                venue=summary.split(" - ")[1].rsplit(",", 1)[0].strip() if summary.count(" - ") >= 2 else "",
                url=r.get("link"), type="", abstract=r.get("snippet"),
                notes=note_join("Google Scholar lead - verify before use",
                                f"cited_by={((r.get('inline_links') or {}).get('cited_by') or {}).get('total')}"
                                if ((r.get('inline_links') or {}).get('cited_by') or {}).get('total') else "")))
        if len(results) < per:
            break
        start += per
        http.sleep(SOURCES["scholar"][2])
    return total, out[:max_n], ["Google Scholar results via SerpApi carry no DOI; verify every lead"]


ADAPTERS = {
    "openalex": search_openalex, "crossref": search_crossref, "semanticscholar": search_semanticscholar,
    "arxiv": search_arxiv, "scopus": search_scopus, "sciencedirect": search_sciencedirect, "wos": search_wos,
    "scholar": search_scholar,
}


def redact(url: str) -> str:
    return re.sub(r"(api_key|apiKey)=[^&]+", r"\1=<KEY>", url)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def save(folder: Path, source: str, qid: str, rows: list[dict], window, query: str, total, notes: list[str]):
    prefix, label, _ = SOURCES[source]
    part = folder / f"03_records_part-{label}.csv"
    existing = read_csv(part) if part.exists() else []
    taken = {r.get("record_id") for r in existing}
    sub_qid = f"{qid}-{prefix}"
    n = sum(1 for r in existing if r.get("query_id") == sub_qid)
    new = []
    for r in rows:
        n += 1
        rid = f"{prefix}-{qid}-{n:04d}"
        while rid in taken:
            n += 1
            rid = f"{prefix}-{qid}-{n:04d}"
        taken.add(rid)
        new.append(dict(r, record_id=rid, source=label, query_id=sub_qid))
    write_csv(part, existing + new, HEADERS[FILES["records"]])
    log_path = folder / FILES["search_log"]
    log = read_csv(log_path) if log_path.exists() else []
    log.append({"query_id": sub_qid, "date": dt.date.today().isoformat(), "source": label, "query_string": query,
                "filters": f"publication years {window[0]}-{window[1]}", "hits": total, "retrieved": len(new),
                "notes": "; ".join(notes) + ("; script: search_sources.py" if notes else "script: search_sources.py")})
    write_csv(log_path, log, HEADERS[FILES["search_log"]])
    return part, len(new)


def next_query_id(folder: Path) -> str:
    log_path = folder / FILES["search_log"]
    nums = [to_int_simple(r.get("query_id", "")) for r in (read_csv(log_path) if log_path.exists() else [])]
    nums = [n for n in nums if n is not None]
    return f"Q{(max(nums) + 1) if nums else 1:02d}"


def to_int_simple(qid: str):
    m = re.match(r"Q(\d+)", qid or "")
    return int(m.group(1)) if m else None


def main(argv=None, transport=urllib_transport, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", help="review folder (litrev-<slug>/)")
    ap.add_argument("--query", required=True, help="Boolean query: AND/OR/NOT, \"phrases\", parentheses")
    ap.add_argument("--sources", default="openalex,crossref,semanticscholar,arxiv",
                    help="comma-separated: " + ",".join(SOURCES))
    ap.add_argument("--window", default="", help="publication years, e.g. 2021-2026 or 2021-present")
    ap.add_argument("--max", type=int, default=300, help="maximum records per source (default 300)")
    ap.add_argument("--query-id", default="", help="query id stem (default: next Qnn in the search log)")
    for s in SOURCES:
        ap.add_argument(f"--q-{s}", default="", help=f"override the translated query for {s}")
    ap.add_argument("--dry-run", action="store_true", help="print request URLs instead of calling the APIs")
    ap.add_argument("--print-queries", action="store_true", help="print web-interface query strings and exit")
    ap.add_argument("--env-file", default="", help="optional .env file with API keys")
    args = ap.parse_args(argv)

    folder = Path(args.folder) if args.folder else None
    window = parse_window(args.window) if args.window else (window_from_protocol(folder) if folder else None) \
        or parse_window("")
    if args.print_queries:
        print(f"Publication window: {window[0]}-{window[1]}\n")
        for k, v in web_interface_queries(args.query, window).items():
            print(f"{k}:\n  {v}\n")
        return 0
    if folder is None:
        ap.error("folder is required unless --print-queries is used")
    if not args.dry_run and not folder.exists():
        print(f"{folder} not found - run init_review.py first")
        return 1

    env = load_env(args.env_file or None)
    http = Http(transport, env.get("CONTACT_EMAIL", ""), sleep)
    qid = args.query_id or next_query_id(folder)
    print(f"Publication window: {window[0]}-{window[1]} · query id {qid}" + (" · DRY RUN" if args.dry_run else ""))
    summary, blocked = [], False
    for source in [s.strip().lower() for s in args.sources.split(",") if s.strip()]:
        if source not in ADAPTERS:
            print(f"  ! unknown source '{source}' (choose from {', '.join(SOURCES)})")
            continue
        q = getattr(args, f"q_{source}") or translate(source, args.query, window)
        try:
            total, rows, notes = ADAPTERS[source](http, q, window, args.max, env, dry=args.dry_run)
        except NetworkBlocked as e:
            print(f"  ✗ {SOURCES[source][1]}: network blocked ({e})")
            blocked = True
            continue
        except ApiError as e:
            hint = {401: "missing or invalid key / not entitled", 403: "not entitled (subscription, IP range or plan)",
                    429: "rate limited"}.get(e.status, "")
            print(f"  ✗ {SOURCES[source][1]}: {e} {('- ' + hint) if hint else ''}")
            summary.append((SOURCES[source][1], "error", str(e)[:80]))
            continue
        if args.dry_run:
            print(f"  · {SOURCES[source][1]}\n      query: {q}\n      first request: {notes[0] if notes else ''}")
            continue
        part, n = save(folder, source, qid, rows, window, q, total, notes)
        print(f"  ✓ {SOURCES[source][1]}: {n} saved of {total} hits -> {part.name}")
        summary.append((SOURCES[source][1], n, total))
    if blocked and not summary:
        print("\nThe network to these APIs is blocked here. Use --dry-run and fetch the printed URLs with the web "
              "fetch tool, use research connectors, or export from the databases and run import_records.py.")
        return 2
    if not args.dry_run:
        print("\nNext: python3 scripts/dedupe_records.py " + str(folder))
    return 0


if __name__ == "__main__":
    sys.exit(main())
