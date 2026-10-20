#!/usr/bin/env python3
"""Find legal open-access full texts for the included studies (needed for three-pass reading).

Usage:
    python3 scripts/find_fulltext.py litrev-<slug>/ [--env-file .env] [--dry-run] [--only REF_ID,...]

For every printable row of 05_verification.csv that has a DOI, the script asks, in order:
  1. Unpaywall   https://api.unpaywall.org/v2/{doi}?email=...   (UNPAYWALL_EMAIL or CONTACT_EMAIL required)
  2. OpenAlex    https://api.openalex.org/works/doi:{doi}          (open_access.oa_url, best_oa_location)
  3. Semantic Scholar  /graph/v1/paper/DOI:{doi}?fields=openAccessPdf,externalIds  (arXiv id as a fallback)
and writes the first hit to 06_fulltext.csv (ref_id, doi, oa_url, oa_source, version, license,
checked_on, notes). Rows without a DOI are listed so you can look for the working-paper version, the
authors' pages or a repository copy by hand. Paywalled studies stay paywalled: ask the user for the PDF
(e.g. through their library) - never use shadow libraries.

Exit code 2 when the network is blocked; --dry-run prints the URLs for the web fetch tool instead.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, PRINTABLE_STATUSES, load_env, norm_doi, read_csv,  # noqa: E402
                           write_csv)
from search_sources import ApiError, Http, NetworkBlocked, urllib_transport  # noqa: E402


def unpaywall(http: Http, doi: str, email: str) -> dict | None:
    data = http.json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?"
                     f"{urllib.parse.urlencode({'email': email})}")
    loc = data.get("best_oa_location") or {}
    url = loc.get("url_for_pdf") or loc.get("url")
    if data.get("is_oa") and url:
        return {"oa_url": url, "oa_source": f"Unpaywall ({loc.get('host_type', '')})",
                "version": loc.get("version") or "", "license": loc.get("license") or ""}
    return None


def openalex(http: Http, doi: str, key: str = "") -> dict | None:
    url = f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}"
    if key:
        url += "?" + urllib.parse.urlencode({"api_key": key})
    data = http.json(url)
    best = data.get("best_oa_location") or {}
    oa = data.get("open_access") or {}
    link = best.get("pdf_url") or best.get("landing_page_url") or oa.get("oa_url")
    if oa.get("is_oa") and link:
        return {"oa_url": link, "oa_source": "OpenAlex", "version": best.get("version") or "",
                "license": best.get("license") or ""}
    return None


def semanticscholar(http: Http, doi: str, key: str = "") -> dict | None:
    url = (f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi, safe='/')}?"
           f"{urllib.parse.urlencode({'fields': 'openAccessPdf,externalIds'})}")
    data = http.json(url, {"x-api-key": key} if key else {})
    pdf = (data.get("openAccessPdf") or {}).get("url")
    if pdf:
        return {"oa_url": pdf, "oa_source": "Semantic Scholar", "version": "", "license": ""}
    arxiv = (data.get("externalIds") or {}).get("ArXiv")
    if arxiv:
        return {"oa_url": f"https://arxiv.org/abs/{arxiv}", "oa_source": "arXiv (via Semantic Scholar)",
                "version": "preprint", "license": ""}
    return None


def main(argv=None, transport=urllib_transport) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--env-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated ref_ids")
    args = ap.parse_args(argv)

    folder = Path(args.folder)
    env = load_env(args.env_file or None)
    email = env.get("UNPAYWALL_EMAIL") or env.get("CONTACT_EMAIL", "")
    rows = [r for r in read_csv(folder / FILES["verification"])
            if (r.get("status") or "").upper() in PRINTABLE_STATUSES]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        rows = [r for r in rows if r.get("ref_id") in wanted]
    with_doi = [r for r in rows if norm_doi(r.get("doi", ""))]
    no_doi = [r for r in rows if not norm_doi(r.get("doi", ""))]

    if args.dry_run:
        for r in with_doi:
            d = norm_doi(r["doi"])
            print(f"{r.get('ref_id')}:")
            if email:
                print(f"  https://api.unpaywall.org/v2/{d}?email={email}")
            print(f"  https://api.openalex.org/works/doi:{d}")
            print(f"  https://api.semanticscholar.org/graph/v1/paper/DOI:{d}?fields=openAccessPdf,externalIds")
        for r in no_doi:
            print(f"{r.get('ref_id')}: no DOI - search the series page, authors' pages or repositories by hand")
        return 0

    http = Http(transport, email)
    out_path = folder / FILES["fulltext"]
    existing = {r["ref_id"]: r for r in read_csv(out_path)} if out_path.exists() else {}
    today = dt.date.today().isoformat()
    found = 0
    for r in with_doi:
        d = norm_doi(r["doi"])
        hit, notes = None, []
        steps = []
        if email:
            steps.append(("Unpaywall", lambda: unpaywall(http, d, email)))
        else:
            notes.append("Unpaywall skipped (set UNPAYWALL_EMAIL)")
        steps += [("OpenAlex", lambda: openalex(http, d, env.get("OPENALEX_API_KEY", ""))),
                  ("Semantic Scholar", lambda: semanticscholar(http, d, env.get("S2_API_KEY", "")))]
        for name, fn in steps:
            try:
                hit = fn()
            except NetworkBlocked as e:
                print(f"Network blocked ({e}). Use --dry-run and the web fetch tool instead.")
                return 2
            except ApiError as e:
                notes.append(f"{name}: {e}"[:80])
                continue
            if hit:
                break
        row = {"ref_id": r["ref_id"], "doi": d, "checked_on": today, "notes": "; ".join(notes)}
        if hit:
            row.update(hit)
            found += 1
        else:
            row["notes"] = "; ".join(notes + ["no open-access copy found - ask the user for the PDF"])
        existing[r["ref_id"]] = row
        print(f"  {'✓' if hit else '·'} {r['ref_id']}: {row.get('oa_url') or row['notes']}")
    for r in no_doi:
        existing.setdefault(r["ref_id"], {"ref_id": r["ref_id"], "checked_on": today,
                                          "notes": "no DOI - check series page / authors' pages / repositories"})
    write_csv(out_path, list(existing.values()), HEADERS[FILES["fulltext"]])
    print(f"\nOpen-access copies found: {found}/{len(with_doi)} with DOI · without DOI: {len(no_doi)}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
