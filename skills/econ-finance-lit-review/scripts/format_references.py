#!/usr/bin/env python3
"""Build an APA 7 reference list from 05_verification.csv.

Usage:
    python3 scripts/format_references.py litrev-<slug>/05_verification.csv --lang tr > refs.md
    python3 scripts/format_references.py 05_verification.csv --lang en --with-status
    python3 scripts/format_references.py 05_verification.csv --include-unverified

Only VERIFIED, PARTIAL and PREPRINT rows enter the list; NOT_VERIFIED and RETRACTED
rows are listed separately with --include-unverified (never as evidence).
Metadata is copied from the CSV, never retyped, so the list is only as good as the
verification log. Titles are printed as stored (no case conversion); store a clean
title if the registry returned one in ALL CAPS - the script warns about those.

Field use by type:
  journal-article  venue=journal, volume, issue, pages
  working-paper / preprint / report  series, number, publisher
  book  publisher;  book-chapter / conference-paper  venue=book or proceedings, pages, publisher
  thesis  series=degree text (e.g. 'Yüksek lisans tezi'), publisher=institution,
          venue=database (e.g. 'YÖK Ulusal Tez Merkezi'), number=thesis no.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (BLOCKED_STATUSES, PRINTABLE_STATUSES, family_name, given_name,  # noqa: E402
                           norm_doi, norm_surname, read_csv, split_authors)

T = {
    "tr": {"and": "ve", "nd": "t.y.", "heading": "Kaynakça", "unverified": "Doğrulanamayan veya geri çekilmiş kaynaklar (kanıt olarak kullanılmadı)",
           "in": "içinde", "pp": "ss.", "p": "s.", "no": "No.", "thesis_no": "Tez No."},
    "en": {"and": "&", "nd": "n.d.", "heading": "References", "unverified": "Unverified or retracted sources (not used as evidence)",
           "in": "In", "pp": "pp.", "p": "p.", "no": "No.", "thesis_no": "No."},
}
STATUS_MARK = {"VERIFIED": "✅", "PARTIAL": "🟡", "PREPRINT": "📄", "NOT_VERIFIED": "⛔", "RETRACTED": "🚨"}


def initials(given: str) -> str:
    out = []
    for token in re.split(r"\s+", given.strip()):
        if not token:
            continue
        parts = [p for p in token.split("-") if p]
        out.append("-".join(p[0].upper() + "." for p in parts if p[0].isalpha()))
    return " ".join(x for x in out if x)


def apa_author(author: str) -> str:
    fam, giv = family_name(author), given_name(author)
    if not giv:
        return fam                           # organization as author
    ini = initials(giv)
    return f"{fam}, {ini}" if ini else fam


def apa_authors(authors: str, lang: str) -> str:
    names = [apa_author(a) for a in split_authors(authors)]
    if not names:
        return ""
    conj = T[lang]["and"]
    if len(names) == 1:
        return names[0]
    if len(names) > 20:
        return ", ".join(names[:19]) + ", . . . " + names[-1]
    if lang == "en":
        return ", ".join(names[:-1]) + f", {conj} " + names[-1]
    return ", ".join(names[:-1]) + f" {conj} " + names[-1]


def end(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def pages_label(pages: str, lang: str) -> str:
    pages = pages.replace("--", "–").replace("-", "–")
    key = "pp" if "–" in pages else "p"
    return f"{T[lang][key]} {pages}"


def clean_doi(doi: str) -> str:
    """Strip resolver prefixes but keep the registrant's casing."""
    doi = (doi or "").strip()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.I)
    return re.sub(r"^doi:\s*", "", doi, flags=re.I).rstrip(".")


def link_of(row: dict) -> str:
    if norm_doi(row.get("doi", "")):
        return f"https://doi.org/{clean_doi(row['doi'])}"
    return (row.get("link") or "").strip()


def format_entry(row: dict, lang: str, year_label: str) -> str:
    authors = apa_authors(row.get("authors", ""), lang)
    title = (row.get("title") or "").strip()
    typ = (row.get("type") or "journal-article").strip()
    venue = (row.get("venue") or "").strip()
    vol, iss = (row.get("volume") or "").strip(), (row.get("issue") or "").strip()
    pages = (row.get("pages") or "").strip()
    series, number = (row.get("series") or "").strip(), (row.get("number") or "").strip()
    publisher = (row.get("publisher") or "").strip()
    tr = T[lang]

    if authors and not authors.endswith("."):
        authors += "."                       # group authors: 'PRISMA-S Group. (2021).'
    head = f"{authors} ({year_label})." if authors else ""
    if typ == "journal-article":
        if not authors:
            head = ""
        body = end(title)
        src = f"*{venue}"
        if vol:
            src += f", {vol}*"
            if iss:
                src += f"({iss})"
        else:
            src += "*"
        if pages:
            src += ", " + pages.replace("--", "–").replace("-", "–")
        body += " " + end(src)
    elif typ in ("working-paper", "preprint", "report"):
        ser = series or (venue if typ == "preprint" else "")
        tail = f" ({ser} {tr['no']} {number})" if ser and number else (f" ({ser})" if ser else "")
        body = f"*{title}*{tail}" + ("" if not tail and title.endswith((".", "?", "!")) else ".")
        if publisher and publisher.lower() not in ser.lower():
            body += f" {end(publisher)}"
    elif typ == "book":
        body = f"*{title}*" + ("" if title.endswith((".", "?", "!")) else ".")
        if publisher:
            body += f" {end(publisher)}"
    elif typ in ("book-chapter", "conference-paper"):
        body = end(title)
        where = f"*{venue}*"
        pg = f" ({pages_label(pages, lang)})" if pages else ""
        body += f" {tr['in']} {where}{pg}." if lang == "en" else f" {where} {tr['in']}{pg}."
        if publisher:
            body += f" {end(publisher)}"
    elif typ == "thesis":
        bracket = ", ".join(x for x in (series, publisher) if x)
        body = f"*{title}*" + (f" [{bracket}]." if bracket else ".")
        if venue:
            body += f" {venue}" + (f" ({tr['thesis_no']} {number})." if number else ".")
    else:
        body = end(title) + (f" {end(venue)}" if venue else "")

    link = link_of(row)
    return " ".join(x for x in (head, body, link) if x)


def sort_key(row: dict) -> tuple:
    fams = tuple(norm_surname(family_name(a)) for a in split_authors(row.get("authors", "")))
    return (fams or (norm_surname(row.get("title", "")),), row.get("year", ""), (row.get("title") or "").lower())


def reference_entries(rows: list[dict], lang: str = "en", with_status: bool = False) -> list[str]:
    """APA 7 entries for printable rows, sorted, with a/b suffixes for same author-year pairs."""
    printable = sorted([r for r in rows if (r.get("status") or "").strip().upper() in PRINTABLE_STATUSES],
                       key=sort_key)
    groups = defaultdict(list)
    for r in printable:
        groups[(apa_authors(r.get("authors", ""), "en"), (r.get("year") or "").strip())].append(r)
    labels = {}
    for (_, year), grp in groups.items():
        year = year or T[lang]["nd"]
        if len(grp) == 1:
            labels[id(grp[0])] = year
        else:
            for i, r in enumerate(sorted(grp, key=lambda x: (x.get("title") or "").lower())):
                labels[id(r)] = f"{year}{chr(97 + i)}"
    out = []
    for r in printable:
        mark = STATUS_MARK.get((r.get("status") or "").upper(), "") + " " if with_status else ""
        out.append(mark + format_entry(r, lang, labels[id(r)]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verification_csv")
    ap.add_argument("--lang", choices=["en", "tr"], default="en", help="en: APA 7 with &; tr: APA 7 with ve (other languages: adapt the connector by hand)")
    ap.add_argument("--with-status", action="store_true", help="prefix each entry with its status mark")
    ap.add_argument("--include-unverified", action="store_true", help="append NOT_VERIFIED/RETRACTED rows in a separate section")
    args = ap.parse_args()

    rows = read_csv(args.verification_csv)
    printable = [r for r in rows if (r.get("status") or "").strip().upper() in PRINTABLE_STATUSES]
    blocked = [r for r in rows if (r.get("status") or "").strip().upper() in BLOCKED_STATUSES]
    other = [r for r in rows if r not in printable and r not in blocked]

    warnings = []
    for r in printable:
        rid = r.get("ref_id") or r.get("title", "")[:40]
        if not link_of(r):
            warnings.append(f"{rid}: no link")
        if not (r.get("link_check_method") or "").strip() or not (r.get("checked_on") or "").strip():
            warnings.append(f"{rid}: link check method/date missing")
        if re.search(r"et al\.?|vd\.|ve ark\.|\.\.\.|…", r.get("authors") or "", re.I):
            warnings.append(f"{rid}: author list is truncated - fetch the full byline (APA lists up to 20)")
        t = r.get("title") or ""
        if len(t) > 12 and t.upper() == t:
            warnings.append(f"{rid}: title is ALL CAPS - store the publisher's casing")
    for r in other:
        warnings.append(f"{r.get('ref_id', '?')}: unknown status '{r.get('status', '')}' - not printed")

    out = [f"## {T[args.lang]['heading']}", ""]
    for entry in reference_entries(printable, args.lang, args.with_status):
        out += [entry, ""]
    if args.include_unverified and blocked:
        out += [f"### {T[args.lang]['unverified']}", ""]
        for r in sorted(blocked, key=sort_key):
            status = (r.get("status") or "").upper()
            label = (r.get("year") or "").strip() or T[args.lang]["nd"]
            out += [f"{STATUS_MARK.get(status, '')} {status}: {format_entry(r, args.lang, label)}", ""]
    print("\n".join(out).rstrip() + "\n")

    print(f"[format_references] printed {len(printable)} entries; "
          f"{len(blocked)} blocked (NOT_VERIFIED/RETRACTED); {len(warnings)} warning(s)", file=sys.stderr)
    for w in warnings:
        print(f"  WARNING {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
