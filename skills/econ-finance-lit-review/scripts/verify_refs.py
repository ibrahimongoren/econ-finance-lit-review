#!/usr/bin/env python3
"""Batch-verify references against Crossref, OpenAlex and the doi.org handle API.

ONLY for environments with open network egress (e.g. Claude Code on a laptop).
In sandboxed chat sessions these hosts are usually blocked from the shell: the
script detects that, says so and exits with code 2 - then follow the ladder in
SKILL.md §6 with the web fetch tool instead.

Usage:
    python3 scripts/verify_refs.py input.csv -o litrev-<slug>/05_verification.csv --mailto you@example.org
    python3 scripts/verify_refs.py --selftest          # offline check of the match logic

input.csv needs some of: record_id or ref_id, doi, title, authors ('Family, Given; ...'), year, type.
Rows with a DOI are looked up by DOI; rows without one by title + first author.
Every candidate must pass the four-part match test (title, first author, year ±1,
venue not contradicted). Rows that cannot be matched are written as NOT_VERIFIED
with a note - never guessed. Grey literature without DOIs (BIS, many central-bank
papers) will usually need a manual landing-page check afterwards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, first_author_family, norm_doi, read_csv,  # noqa: E402
                           surname_match, title_similarity, to_int, write_csv)

UA = "econ-finance-lit-review/1.0 (literature verification; mailto:{mailto})"
PREPRINT_TYPES = {"posted-content", "report", "report-component", "working-paper", "preprint"}


class NetworkBlocked(RuntimeError):
    pass


class Client:
    def __init__(self, mailto: str, pause: float):
        self.mailto = mailto or "anonymous@example.org"
        self.pause = pause
        self.last = 0.0

    def get_json(self, url: str, tries: int = 3):
        for attempt in range(tries):
            wait = self.pause - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={"User-Agent": UA.format(mailto=self.mailto)})
            self.last = time.time()
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code == 429 and attempt < tries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                if e.code in (403, 407):
                    raise NetworkBlocked(f"{url} -> HTTP {e.code}")
                return None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                raise NetworkBlocked(f"{url} -> {e}")
        return None

    def crossref_doi(self, doi):
        data = self.get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
                             + "?mailto=" + urllib.parse.quote(self.mailto))
        return data.get("message") if data else None

    def crossref_search(self, title, author, rows=5):
        q = {"query.bibliographic": title, "rows": rows, "mailto": self.mailto}
        if author:
            q["query.author"] = author
        data = self.get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(q))
        return (data or {}).get("message", {}).get("items", []) if data else []

    def openalex_doi(self, doi):
        return self.get_json("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/")
                             + "?mailto=" + urllib.parse.quote(self.mailto))

    def doi_resolves(self, doi):
        data = self.get_json("https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/"))
        return bool(data and data.get("responseCode") == 1)


def from_crossref(m: dict) -> dict:
    def year_of(key):
        parts = (m.get(key) or {}).get("date-parts") or [[None]]
        return parts[0][0] if parts and parts[0] else None
    authors = "; ".join(
        f"{a.get('family', '').strip()}, {a.get('given', '').strip()}".strip(", ")
        if a.get("family") else a.get("name", "") for a in m.get("author", []))
    print_year = year_of("published-print") or year_of("issued")
    online_year = year_of("published-online")
    retracted = any((u.get("type") or "").lower() in ("retraction", "removal")
                    for u in m.get("update-to", []) or [])
    return {
        "title": (m.get("title") or [""])[0], "authors": authors, "year": print_year or "",
        "online_year": online_year if online_year and online_year != print_year else "",
        "venue": (m.get("container-title") or [""])[0], "volume": m.get("volume", ""),
        "issue": m.get("issue", ""), "pages": m.get("page", "") or m.get("article-number", ""),
        "doi": m.get("DOI", ""), "type": m.get("type", ""), "publisher": m.get("publisher", ""),
        "retracted": "Y" if retracted else "",
    }


def match_test(src: dict, rec: dict) -> tuple[bool, list[str]]:
    """Four-part test. Missing input fields are not held against the record."""
    problems = []
    if src.get("title"):
        sim = title_similarity(src["title"], rec.get("title", ""))
        if sim < 0.90:
            problems.append(f"title similarity {sim:.2f}")
    fa, fr = first_author_family(src.get("authors", "")), first_author_family(rec.get("authors", ""))
    if fa and fr and not surname_match(fa, fr):
        problems.append(f"first author {fa!r} vs {fr!r}")
    ys = to_int(src.get("year"))
    yr = {to_int(rec.get("year")), to_int(rec.get("online_year"))} - {None}
    if ys and yr and min(abs(ys - y) for y in yr) > 1:
        problems.append(f"year {ys} vs {sorted(yr)}")
    sv, rv = (src.get("venue") or "").lower(), (rec.get("venue") or "").lower()
    if sv and rv and title_similarity(sv, rv) < 0.6 and src.get("type") not in ("working-paper", "preprint"):
        problems.append(f"venue {src.get('venue')!r} vs {rec.get('venue')!r}")
    return (not problems), problems


def verify_row(c: Client, src: dict, use_openalex: bool) -> dict:
    today = dt.date.today().isoformat()
    out = {"ref_id": src.get("ref_id") or src.get("record_id", ""), "record_id": src.get("record_id", ""),
           "checked_on": today, "language": src.get("language", "")}
    notes, rec, method = [], None, ""

    doi = norm_doi(src.get("doi", ""))
    if doi:
        m = c.crossref_doi(doi)
        if m:
            rec, method = from_crossref(m), "crossref:doi"
        else:
            notes.append("DOI not found in Crossref")
    if rec is None and src.get("title"):
        for item in c.crossref_search(src["title"], first_author_family(src.get("authors", ""))):
            cand = from_crossref(item)
            ok, _ = match_test(src, cand)
            if ok:
                rec, method = cand, "crossref:title-search"
                if doi and norm_doi(cand["doi"]) != doi:
                    notes.append(f"input DOI {doi} differs from matched record {cand['doi']}")
                break
    if rec is None:
        out.update({k: src.get(k, "") for k in ("title", "authors", "year", "venue", "doi", "type")})
        out.update(status="NOT_VERIFIED", confidence="", method="none",
                   discrepancy_note="; ".join(notes + ["no registry record passed the match test - check landing page manually"]))
        return out

    ok, problems = match_test(src, rec)
    out.update(rec)
    out["method"] = method
    if use_openalex and rec.get("doi"):
        oa = c.openalex_doi(rec["doi"])
        if oa:
            if oa.get("is_retracted"):
                out["retracted"] = "Y"
            if oa.get("is_paratext"):
                notes.append("OpenAlex marks this as paratext (front matter/editorial)")
            oa_url = (oa.get("open_access") or {}).get("oa_url")
            if oa_url:
                notes.append(f"OA copy: {oa_url}")
    if rec.get("doi") and c.doi_resolves(rec["doi"]):
        out["link"] = f"https://doi.org/{rec['doi']}"
        out["link_check_method"] = "doi.org handle API"
    elif rec.get("doi"):
        notes.append("doi.org handle API did not confirm the DOI")

    is_preprint = rec.get("type") in PREPRINT_TYPES or norm_doi(rec.get("doi", "")).startswith("10.2139/ssrn")
    if out.get("retracted") == "Y":
        status = "RETRACTED"
    elif not ok:
        status = "PARTIAL"
        notes.extend(problems)
    elif not out.get("link"):
        status = "PARTIAL"
    else:
        status = "PREPRINT" if is_preprint else "VERIFIED"
    out.update(status=status, confidence="High" if status in ("VERIFIED", "PREPRINT", "RETRACTED") else "Medium",
               discrepancy_note="; ".join(notes),
               type={"journal-article": "journal-article", "posted-content": "preprint",
                     "report": "working-paper", "book-chapter": "book-chapter",
                     "proceedings-article": "conference-paper", "book": "book",
                     "dissertation": "thesis"}.get(rec.get("type", ""), rec.get("type", "")))
    return out


def selftest() -> int:
    src = {"title": "Two-way fixed effects estimators with heterogeneous treatment effects",
           "authors": "de Chaisemartin, Clément; D'Haultfoeuille, Xavier", "year": "2020",
           "venue": "American Economic Review"}
    good = {"title": "Two-Way Fixed Effects Estimators with Heterogeneous Treatment Effects",
            "authors": "Chaisemartin, Clément de; D'Haultfœuille, Xavier", "year": 2020,
            "venue": "American Economic Review"}
    near_miss = {"title": "Two-Way Fixed Effects and Differences-in-Differences Estimators with Several Treatments",
                 "authors": "de Chaisemartin, Clément; D'Haultfœuille, Xavier", "year": 2023,
                 "venue": "Journal of Econometrics"}
    wp_year = dict(good, year=2018)
    checks = [
        ("exact record passes", match_test(src, good)[0] is True),
        ("near-miss title fails", match_test(src, near_miss)[0] is False),
        ("year off by 2 fails", match_test(src, wp_year)[0] is False),
        ("online-first year within 1 passes", match_test(dict(src, year="2021"), good)[0] is True),
    ]
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
    return 0 if all(p for _, p in checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?")
    ap.add_argument("-o", "--output", default="05_verification.csv")
    ap.add_argument("--mailto", default="", help="contact e-mail for the Crossref/OpenAlex polite pool")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between requests (default 1.0)")
    ap.add_argument("--no-openalex", action="store_true", help="skip OpenAlex retraction/OA enrichment")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.input:
        ap.error("input CSV required (or --selftest)")

    rows = read_csv(args.input)
    c = Client(args.mailto, args.pause)
    try:
        c.get_json("https://api.crossref.org/works/10.1257%2Faer.20181169")
    except NetworkBlocked as e:
        print(f"Network to the registries is blocked here ({e}).\n"
              "Use the web fetch ladder in SKILL.md §6 instead; nothing was written.")
        return 2

    results = []
    for i, src in enumerate(rows, 1):
        try:
            res = verify_row(c, src, not args.no_openalex)
        except NetworkBlocked as e:
            print(f"Stopped at row {i}: network blocked ({e}). Partial results written.")
            break
        results.append(res)
        print(f"[{i}/{len(rows)}] {res['status']:<12} {res.get('ref_id') or res.get('title', '')[:60]}")
        write_csv(args.output, results, HEADERS[FILES["verification"]])   # save as we go

    tally = {}
    for r in results:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("Tally: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
