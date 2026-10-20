#!/usr/bin/env python3
"""Import search exports from Web of Science, Scopus, ScienceDirect, Google Scholar (Publish or Perish),
Zotero, any reference manager, or research connectors (Consensus, Elicit, SciSpace, MCP servers) into
the review folder.

Usage:
    python3 scripts/import_records.py litrev-<slug>/ savedrecs.txt [more files...] [--source "Web of Science"]
        [--query "TS=(...) AND PY=(2021-2026)"] [--window 2021-2026]

Recognized formats (detected from content, not the file name):
  RIS (.ris)                 Scopus, ScienceDirect, Web of Science, Zotero, EndNote, Mendeley exports
  BibTeX (.bib)              Scopus, ScienceDirect, Web of Science, Zotero, Google Scholar exports
  Web of Science plain text  "FN Clarivate ... / PT J / AU ... / ER" tagged records
  Web of Science tab-delim.  header row of two-letter tags (PT AU AF TI SO ... UT)
  Scopus CSV                 columns such as Authors, Author full names, Title, Year, Source title, DOI, EID
  Publish or Perish CSV      columns such as Cites, Authors, Title, Year, Source, ArticleURL, DOI
  Zotero CSV                 columns such as Item Type, Publication Year, Author, Title, Publication Title
  Generic CSV                any CSV with recognizable title/author/year/DOI columns
  JSON / JSON Lines          connector or MCP results: a list of objects (or {"papers": [...]},
                             {"results": [...]}, {"data": [...]}) with title, authors (list or "A; B"),
                             year or date, doi, url, venue/journal, abstract, citations. SciSpace,
                             Semantic Scholar, OpenAlex and Crossref field names are recognized.

Each file becomes 03_records_part-<Source>.csv (record ids <PREFIX>-<n>) plus one 02_search_log.csv row
(query_id I<nn>-<PREFIX>) so PRISMA and the coverage check count it. Paste the exact query you ran in
the database with --query - it belongs in the methods section. With --window, rows whose year falls
outside the window are reported (not dropped): screen them out with code E7 at Stage 4.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, in_window, norm_doi, parse_window, read_csv,  # noqa: E402
                           to_int, write_csv)

PARTICLES = {"de", "da", "del", "der", "di", "du", "van", "von", "le", "la", "dos", "das", "ter", "ten"}
WOS_TYPE = {"J": "journal-article", "B": "book", "S": "book-chapter", "P": "conference-paper"}
RIS_TYPE = {"JOUR": "journal-article", "JFULL": "journal-article", "EJOUR": "journal-article",
            "BOOK": "book", "CHAP": "book-chapter", "CONF": "conference-paper", "CPAPER": "conference-paper",
            "RPRT": "working-paper", "THES": "thesis", "UNPB": "preprint", "GEN": "other"}
BIB_TYPE = {"article": "journal-article", "book": "book", "incollection": "book-chapter",
            "inproceedings": "conference-paper", "techreport": "working-paper", "phdthesis": "thesis",
            "mastersthesis": "thesis", "unpublished": "preprint", "misc": "other"}


def blank() -> dict:
    return {k: "" for k in HEADERS[FILES["records"]]}


def given_first_to_family(name: str) -> str:
    """'Jane Q. Doe' -> 'Doe, Jane Q.'; 'JL Harper' -> 'Harper, JL'; keeps 'Doe, Jane'."""
    name = re.sub(r"\s+", " ", (name or "").strip().strip(","))
    if not name or "," in name:
        return name
    parts = name.split(" ")
    if len(parts) == 1:
        return name
    i = len(parts) - 1
    while i - 1 > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return f"{' '.join(parts[i:])}, {' '.join(parts[:i])}"


def join_authors(names) -> str:
    return "; ".join(n for n in (given_first_to_family(x) for x in names) if n)


def pages(start: str, end: str) -> str:
    start, end = (start or "").strip(), (end or "").strip()
    return f"{start}-{end}" if start and end else (start or end)


# ---------------------------------------------------------------------------
# Format readers -> list of record dicts (without record_id/source/query_id)
# ---------------------------------------------------------------------------
def read_ris(text: str) -> list[dict]:
    out, cur, multi = [], None, {}
    for raw in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", raw)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur, multi = blank(), {"AU": [], "A1": [], "KW": []}
            cur["type"] = RIS_TYPE.get(val, "other")
        elif cur is None:
            continue
        elif tag == "ER":
            authors = multi["AU"] or multi["A1"]
            cur["authors"] = join_authors(authors)
            out.append(cur)
            cur = None
        elif tag in ("AU", "A1"):
            multi[tag].append(val)
        elif tag in ("TI", "T1") and not cur["title"]:
            cur["title"] = val
        elif tag in ("PY", "Y1", "DA") and not cur["year"]:
            cur["year"] = str(to_int(val) or "")
        elif tag in ("T2", "JO", "JF", "JA", "SE", "BT") and not cur["venue"]:
            cur["venue"] = val
        elif tag == "VL":
            cur["volume"] = val
        elif tag == "IS":
            cur["issue"] = val
        elif tag == "SP":
            cur["pages"] = val
        elif tag == "EP":
            cur["pages"] = pages(cur["pages"], val)
        elif tag == "DO":
            cur["doi"] = norm_doi(val)
        elif tag in ("UR", "L1", "L2") and not cur["url"]:
            cur["url"] = val
        elif tag in ("AB", "N2") and not cur["abstract"]:
            cur["abstract"] = val
        elif tag == "LA":
            cur["language"] = val
    return out


def _bib_fields(body: str) -> dict:
    fields, i, n = {}, 0, len(body)
    while i < n:
        m = re.match(r"\s*,?\s*([A-Za-z][\w-]*)\s*=\s*", body[i:])
        if not m:
            break
        key = m.group(1).lower()
        i += m.end()
        if i < n and body[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                depth += {"{": 1, "}": -1}.get(body[j], 0)
                j += 1
            val, i = body[i + 1:j - 1], j
        elif i < n and body[i] == '"':
            j = i + 1
            while j < n and not (body[j] == '"' and body[j - 1] != "\\"):
                j += 1
            val, i = body[i + 1:j], j + 1
        else:
            m2 = re.match(r"[^,]+", body[i:])
            val = m2.group(0).strip() if m2 else ""
            i += m2.end() if m2 else 1
        fields[key] = re.sub(r"\s+", " ", val.replace("{", "").replace("}", "")).strip()
    return fields


def read_bibtex(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"@(\w+)\s*\{\s*[^,]*,", text):
        etype = m.group(1).lower()
        if etype in ("comment", "string", "preamble"):
            continue
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        f = _bib_fields(text[m.end():j - 1])
        r = blank()
        r["type"] = BIB_TYPE.get(etype, "other")
        r["title"] = f.get("title", "")
        r["authors"] = join_authors(a for a in re.split(r"\s+and\s+", f.get("author", "")) if a.strip())
        r["year"] = str(to_int(f.get("year", "")) or "")
        r["venue"] = f.get("journal") or f.get("booktitle") or f.get("series") or f.get("institution", "")
        r["volume"], r["issue"] = f.get("volume", ""), f.get("number", "")
        r["pages"] = f.get("pages", "").replace("--", "-")
        r["doi"] = norm_doi(f.get("doi", ""))
        r["url"] = f.get("url", "")
        r["abstract"] = f.get("abstract", "")
        r["language"] = f.get("language", "")
        out.append(r)
    return out


def read_wos_plain(text: str) -> list[dict]:
    out, cur, last = [], None, None
    for raw in text.splitlines():
        tag, val = raw[:2], raw[3:].rstrip()
        if tag == "  " and cur is not None and last:
            cur.setdefault(last, []).append(val.strip())
            continue
        if tag in ("FN", "VR", "EF"):
            continue
        if tag == "PT":
            cur, last = {"PT": [val.strip()]}, "PT"
        elif tag == "ER":
            if cur:
                out.append(_wos_to_record({k: v for k, v in cur.items()}))
            cur, last = None, None
        elif cur is not None and re.match(r"^[A-Z][A-Z0-9]$", tag):
            cur.setdefault(tag, []).append(val.strip())
            last = tag
    return out


def _wos_to_record(t: dict) -> dict:
    def one(tag, sep=" "):
        return sep.join(t.get(tag, [])).strip()
    r = blank()
    names = t.get("AF") or t.get("AU") or []
    if len(names) == 1 and ";" in names[0]:
        names = [n.strip() for n in names[0].split(";")]
    r["authors"] = join_authors(names)
    r["title"], r["venue"] = one("TI"), one("SO")
    r["year"] = str(to_int(one("PY")) or "")
    r["volume"], r["issue"] = one("VL"), one("IS")
    r["pages"] = pages(one("BP"), one("EP")) or one("AR")
    r["doi"] = norm_doi(one("DI"))
    r["abstract"], r["language"] = one("AB"), one("LA")
    pt = one("PT")
    r["type"] = "journal-article" if "Article" in one("DT") or pt == "J" else WOS_TYPE.get(pt, one("DT"))
    r["notes"] = f"wos_uid={one('UT')}" if one("UT") else ""
    return r


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def _pick(row: dict, *names) -> str:
    idx = {_norm_header(k): v for k, v in row.items()}
    for n in names:
        v = idx.get(_norm_header(n))
        if v not in (None, ""):
            return str(v).strip()
    return ""


def read_csv_export(text: str, flavour: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), dialect="excel-tab" if flavour == "wos_tab" else "excel")
    out = []
    for row in reader:
        if flavour == "wos_tab":
            out.append(_wos_to_record({k.strip(): [v] for k, v in row.items() if k and v}))
            continue
        r = blank()
        if flavour == "scopus":
            full = _pick(row, "Author full names")
            if full:
                names = [re.sub(r"\s*\(\d+\)\s*$", "", n).strip() for n in full.split(";")]
            else:
                names = [n.strip() for n in _pick(row, "Authors", "Author(s)").split(";")]
            r["authors"] = join_authors(n for n in names if n)
            r["pages"] = pages(_pick(row, "Page start"), _pick(row, "Page end")) or _pick(row, "Art. No.")
            r["type"] = "journal-article" if _pick(row, "Document Type").lower() == "article" \
                else _pick(row, "Document Type").lower()
            eid = _pick(row, "EID")
            r["notes"] = "; ".join(x for x in (f"eid={eid}" if eid else "",
                                               f"cited_by={_pick(row, 'Cited by')}" if _pick(row, "Cited by") else "") if x)
        elif flavour == "pop":
            r["authors"] = join_authors(a for a in _pick(row, "Authors").split(",") if a.strip() and "…" not in a)
            r["pages"] = pages(_pick(row, "StartPage"), _pick(row, "EndPage"))
            r["type"] = _pick(row, "Type").lower()
            r["notes"] = "; ".join(x for x in (f"cited_by={_pick(row, 'Cites')}" if _pick(row, "Cites") else "",
                                               "Publish or Perish export - verify before use") if x)
        elif flavour == "zotero":
            r["authors"] = "; ".join(a.strip() for a in _pick(row, "Author").split(";") if a.strip())
            r["type"] = {"journalarticle": "journal-article", "report": "working-paper", "book": "book",
                         "booksection": "book-chapter", "thesis": "thesis",
                         "preprint": "preprint"}.get(_norm_header(_pick(row, "Item Type")), "other")
            r["pages"] = _pick(row, "Pages")
        else:
            r["authors"] = "; ".join(a.strip() for a in re.split(r";", _pick(row, "Authors", "Author", "Creator"))
                                     if a.strip())
            r["pages"] = _pick(row, "Pages")
            r["type"] = _pick(row, "Type", "Document Type").lower()
        r["title"] = _pick(row, "Title", "Document title", "Article Title")
        r["year"] = str(to_int(_pick(row, "Year", "Publication Year", "PY", "Date")) or "")
        r["venue"] = _pick(row, "Source title", "Source Title", "Publication Title", "Source", "Journal")
        r["volume"], r["issue"] = _pick(row, "Volume"), _pick(row, "Issue", "Number")
        r["doi"] = norm_doi(_pick(row, "DOI"))
        r["url"] = _pick(row, "Link", "ArticleURL", "Url", "URL")
        r["abstract"] = _pick(row, "Abstract", "Abstract Note")
        r["language"] = _pick(row, "Language of Original Document", "Language")
        if r["title"]:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# JSON from research connectors and MCP servers
# ---------------------------------------------------------------------------
LIST_KEYS = ("papers", "results", "data", "items", "records", "works", "hits", "organic_results", "message")


def _get(obj: dict, *paths):
    """First non-empty value among dotted paths, e.g. 'journal.display_name'."""
    for path in paths:
        cur = obj
        for part in path.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur not in (None, "", [], {}):
            return cur
    return None


def _authors_from(value) -> str:
    if isinstance(value, dict):                       # SciSpace {"total": n, "data": [...]}
        value = value.get("data") or value.get("authors") or []
    names = []
    if isinstance(value, str):
        if ";" in value:
            names = value.split(";")
        elif " and " in value:
            names = value.split(" and ")
        elif value.count(",") >= 2:
            names = value.split(",")
        else:
            names = [value]
    elif isinstance(value, list):
        for a in value:
            if isinstance(a, str):
                names.append(a)
            elif isinstance(a, dict):
                if a.get("family"):
                    names.append(f"{a['family']}, {a.get('given', '')}".strip(", "))
                else:
                    names.append(a.get("name") or a.get("display_name") or a.get("displayName")
                                 or (a.get("author") or {}).get("display_name", "") or "")
    return join_authors(n.strip() for n in names if n and n.strip() and "…" not in n
                        and n.strip().lower() not in ("et al.", "et al"))


def _json_record(o: dict) -> dict:
    r = blank()
    title = _get(o, "title", "display_name", "name")
    r["title"] = (title[0] if isinstance(title, list) and title else str(title or "")).strip()
    r["authors"] = _authors_from(_get(o, "authors", "author", "authorships", "creators") or [])
    year = _get(o, "year", "publication_year", "publicationYear", "pub_year", "date", "publicationDate",
                "published", "issued.date-parts", "coverDate")
    r["year"] = str(to_int(json.dumps(year) if isinstance(year, (list, dict)) else year) or "")
    doi = _get(o, "doi", "DOI", "externalIds.DOI", "ids.doi")
    url = _get(o, "url", "link", "paper_url", "landing_page_url", "primary_location.landing_page_url",
               "paper_urls.data.Html", "URL")
    url = url[0] if isinstance(url, list) and url else url
    if not doi and isinstance(url, str) and "doi.org/" in url:
        doi = url
    r["doi"] = norm_doi(str(doi or ""))
    r["url"] = str(url or (o.get("id") if str(o.get("id", "")).startswith("http") else "") or "")
    venue = _get(o, "venue", "journal", "journal_name", "source", "container-title", "container_title",
                 "publication", "primary_location.source.display_name", "publicationName")
    if isinstance(venue, dict):
        venue = venue.get("display_name") or venue.get("name") or ""
    if isinstance(venue, list):
        venue = venue[0] if venue else ""
    r["venue"] = str(venue or "")
    r["volume"], r["issue"] = str(_get(o, "volume", "biblio.volume") or ""), str(_get(o, "issue", "biblio.issue") or "")
    r["pages"] = str(_get(o, "pages", "page") or "")
    abstract = _get(o, "abstract", "summary", "snippet", "tldr")
    r["abstract"] = (abstract.get("text", "") if isinstance(abstract, dict) else str(abstract or "")).strip()
    kind = _get(o, "type", "publication_type", "publicationTypes")
    r["type"] = (", ".join(kind) if isinstance(kind, list) else str(kind or "")).lower()
    cites = _get(o, "citations", "citation_count", "citationCount", "cited_by_count", "metrics.citations.total",
                 "is-referenced-by-count")
    oa = _get(o, "fulltext_url", "openAccessPdf.url", "open_access.oa_url", "oa_url", "pdf_url")
    notes = [f"cited_by={cites}" if isinstance(cites, (int, str)) and str(cites).strip() else "",
             f"oa_url={oa}" if isinstance(oa, str) and oa.startswith("http") else "",
             "connector lead - verify before use"]
    r["notes"] = "; ".join(n for n in notes if n)
    return r


def read_json(text: str) -> list[dict]:
    text = text.strip().lstrip("\ufeff")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        for key in LIST_KEYS:
            val = data.get(key)
            if isinstance(val, dict):
                val = next((v for k2 in LIST_KEYS for v in [val.get(k2)] if isinstance(v, list)), None)
            if isinstance(val, list):
                data = val
                break
        else:
            data = [data]
    out = [_json_record(o) for o in data if isinstance(o, dict)]
    return [r for r in out if r["title"]]


def detect(text: str) -> str:
    head = text.lstrip("\ufeff")[:4000]
    stripped = head.lstrip()
    if stripped[:1] in ("[", "{"):
        return "json"
    first = head.splitlines()[0] if head.splitlines() else ""
    if re.search(r"^TY  - ", head, re.M):
        return "ris"
    if re.search(r"@\w+\s*\{", head):
        return "bibtex"
    if head.startswith("FN ") or re.search(r"^PT [A-Z]\s*$", head, re.M):
        return "wos_plain"
    cols = {_norm_header(c) for c in re.split(r"[\t,]", first)}
    if "\t" in first and {"pt", "au", "ti"} <= cols:
        return "wos_tab"
    if {"eid", "sourcetitle"} & cols and "title" in cols:
        return "scopus"
    if {"cites", "articleurl"} <= cols or {"cites", "gsrank"} <= cols:
        return "pop"
    if {"itemtype", "publicationyear"} <= cols:
        return "zotero"
    if "title" in cols or "documenttitle" in cols:
        return "csv"
    return "unknown"


READERS = {"ris": read_ris, "bibtex": read_bibtex, "wos_plain": read_wos_plain, "json": read_json}
DEFAULT_SOURCE = {"wos_plain": "Web of Science", "wos_tab": "Web of Science", "scopus": "Scopus",
                  "pop": "Publish or Perish", "zotero": "Zotero"}


def prefix_for(source: str) -> str:
    known = {"web of science": "WS", "scopus": "SC", "sciencedirect": "SD", "google scholar": "GS",
             "publish or perish": "PP", "zotero": "ZT", "econlit": "EL", "dergipark": "DP",
             "consensus": "CN", "elicit": "EC", "scispace": "SS", "semantic scholar": "S2", "openalex": "OA",
             "crossref": "CR", "arxiv": "AX", "core": "CO", "repec": "RP", "ideas": "RP", "ssrn": "SR",
             "nber": "NB", "econbiz": "EB", "paper-search": "PS", "tr dizin": "TD"}
    s = source.lower()
    for k, v in known.items():
        if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", s):
            return v
    letters = re.sub(r"[^A-Za-z]", "", source).upper()
    return (letters[:2] or "IM")


def parse_file(path: Path) -> tuple[str, list[dict]]:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    fmt = detect(text)
    if fmt in READERS:
        return fmt, READERS[fmt](text)
    if fmt in ("wos_tab", "scopus", "pop", "zotero", "csv"):
        return fmt, read_csv_export(text.lstrip("﻿"), fmt)
    return fmt, []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--source", default="", help="database name (default: detected from the format)")
    ap.add_argument("--query", default="", help="the exact query run in the database (for the search log)")
    ap.add_argument("--window", default="", help="publication years to check against, e.g. 2021-2026")
    args = ap.parse_args(argv)

    folder = Path(args.folder)
    if not folder.exists():
        print(f"{folder} not found - run init_review.py first")
        return 1
    window = parse_window(args.window) if args.window else None
    log_path = folder / FILES["search_log"]
    log = read_csv(log_path) if log_path.exists() else []
    status = 0
    for f in args.files:
        path = Path(f)
        fmt, rows = parse_file(path)
        if not rows:
            print(f"  ✗ {path.name}: no records recognized (format: {fmt})")
            status = 1
            continue
        source = args.source or DEFAULT_SOURCE.get(fmt, path.stem)
        prefix = prefix_for(source)
        label = re.sub(r"[^A-Za-z0-9]+", "", source.title()) or "Import"
        nums = [int(m.group(1)) for r in log if (m := re.match(r"I(\d+)-", r.get("query_id", "")))]
        qid = f"I{(max(nums) + 1) if nums else 1:02d}-{prefix}"
        part = folder / f"03_records_part-{label}.csv"
        existing = read_csv(part) if part.exists() else []
        taken = {r.get("record_id") for r in existing}
        n, new = len(existing), []
        for r in rows:
            n += 1
            rid = f"{prefix}-{n:05d}"
            while rid in taken:
                n += 1
                rid = f"{prefix}-{n:05d}"
            taken.add(rid)
            new.append(dict(r, record_id=rid, source=source, query_id=qid))
        write_csv(part, existing + new, HEADERS[FILES["records"]])
        outside = [r for r in new if window and in_window(r["year"], window) is False]
        unknown_year = [r for r in new if not r["year"]]
        log.append({"query_id": qid, "date": dt.date.today().isoformat(), "source": source,
                    "query_string": args.query or "(not recorded - add the exact database query)",
                    "filters": f"publication years {window[0]}-{window[1]}" if window else "",
                    "hits": len(rows), "retrieved": len(new),
                    "notes": f"imported from {path.name} ({fmt})"})
        print(f"  ✓ {path.name}: {len(new)} records ({fmt}) -> {part.name} · query id {qid}"
              + (f" · {len(outside)} outside the window (screen out with E7)" if outside else "")
              + (f" · {len(unknown_year)} without a year" if unknown_year else ""))
    write_csv(log_path, log, HEADERS[FILES["search_log"]])
    if not args.query:
        print("Note: record the exact database query in 02_search_log.csv (methods and PRISMA-S need it).")
    print("Next: python3 scripts/dedupe_records.py " + str(folder))
    return status


if __name__ == "__main__":
    sys.exit(main())
