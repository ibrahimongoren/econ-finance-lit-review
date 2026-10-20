#!/usr/bin/env python3
"""Audit a draft review against the verification log before delivery.

Usage:
    python3 scripts/audit_citations.py litrev-<slug>/10_report.md litrev-<slug>/05_verification.csv
    python3 scripts/audit_citations.py report.docx 05_verification.csv --strict

Accepts .md, .txt or .docx. Parsing stops at the reference-list heading
(References, Bibliography, Kaynakça, Referencias, Références, Literaturverzeichnis, ...).

Checks
  1. every in-text citation (author-date; English, Turkish, Spanish, Portuguese,
     French, German and Italian connectors) matches a row in
     the verification log by first-author surname and year;
  2. no citation points only at a NOT_VERIFIED or RETRACTED row;
  3. every printable row (VERIFIED / PARTIAL / PREPRINT) has a link and a recorded
     link check (method + date);
  4. printable rows never cited are listed (an error with --strict).
Exit code 1 when a blocking problem is found, so it can gate delivery.
Heuristic parser: read the 'no entry' list - a flagged phrase may be a false positive.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (BLOCKED_STATUSES, PRINTABLE_STATUSES, first_author_family,  # noqa: E402
                           norm_doi, read_csv, surname_match, to_int)

YEAR = r"(?:1[89]\d{2}|20\d{2})[a-z]?"
REF_HEADING = re.compile(r"^\s*(#+\s*)?(\d+\.?\s*)?(kaynakça|kaynaklar|references|bibliography|reference list|"
                         r"referencias|bibliografía|bibliografia|références|bibliographie|referências|"
                         r"literaturverzeichnis|literatur|riferimenti bibliografici)\s*(\{#[^}]*\})?\s*$", re.I | re.M)
PAREN = re.compile(r"\(([^()]*?\b" + YEAR + r"\b[^()]*)\)")
NARRATIVE = re.compile(r"\((" + YEAR + r"(?:\s*[,;]\s*" + YEAR + r")*)\)")
ETAL = re.compile(r"\s*(et al\.?|vd\.?|ve ark\.?|ve diğerleri|u\. ?a\.|y col\.|e col\.)\s*$", re.I)
PREFIX = re.compile(r"^(e\.g\.,?|i\.e\.,?|see also|see|cf\.|örn\.|örneğin|bkz\.|ayrıca bkz\.|ayrıca|"
                    r"véase|ver|vgl\.|voir|por ejemplo|z\. ?b\.)\s+", re.I)
CONJ_WORDS = ("&", "and", "ve", "y", "e", "et", "und")
CONJ = re.compile(r"\s+(?:&|and|ve|y|e|et|und)\s+|,\s+", re.I)
STOP = {"table", "tablo", "figure", "şekil", "sekil", "section", "bölüm", "bolum", "appendix", "ek",
        "chapter", "the", "in", "since", "until", "between", "from", "and", "ve", "covid", "covid-19",
        "q1", "q2", "q3", "q4", "vol", "no", "cilt", "sayı", "eq", "denklem", "tabla", "tabelle",
        "tableau", "figura", "abbildung", "gráfico", "grafik", "cuadro", "anexo", "anhang"}


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
            text = text.replace(a, b)
        return text
    return path.read_text(encoding="utf-8")


def clean_surname(token: str) -> str:
    token = token.strip(" .,;:*_[]")
    token = re.split(r"['’](?=[a-zçğıöşü]{1,6}\b)", token)[0]     # Turkish suffix: Kasy'ye
    return token


def valid_surname(token: str) -> bool:
    """Capitalised word that is not a known non-name; acronyms (OECD, IMF, TCMB) allowed."""
    return len(token) >= 2 and token[0].isupper() and token.lower() not in STOP


def years_of(text: str) -> list[str]:
    return re.findall(YEAR, text)


def parse_parenthetical(inner: str) -> list[tuple[str, str]]:
    out = []
    for seg in re.split(r";", inner):
        seg = PREFIX.sub("", seg.strip())
        m = re.match(r"^(?P<names>.+?),\s*(?P<years>(?:" + YEAR + r"|t\.y\.|n\.d\.)(?:\s*,\s*" + YEAR + r")*)"
                     r"(?:\s*,\s*(?:s|ss|p|pp|sf)\.?\s*[\w–-]+)?\s*$", seg)
        if not m:
            continue
        names = ETAL.sub("", m.group("names")).strip()
        first = clean_surname(CONJ.split(names)[0]) if names else ""
        first_parts = first.split()
        if not first_parts:
            continue
        surname = " ".join(first_parts[-2:]) if len(first_parts) > 1 and first_parts[0].islower() else first_parts[-1]
        if not valid_surname(surname.split()[-1]):
            continue
        for y in years_of(m.group("years")):
            out.append((surname, y))
    return out


def parse_narrative(text: str) -> list[tuple[str, str, int]]:
    out = []
    for m in NARRATIVE.finditer(text):
        before = text[max(0, m.start() - 120):m.start()].rstrip()
        before = re.sub(r"['’][a-zçğıöşü]{1,6}$", "", before)       # 'vd.'nin (2020)' -> 'vd.'
        before = ETAL.sub("", before)
        tokens = re.findall(r"[^\s(),;]+", before)
        if not tokens:
            continue
        # walk back over 'A ve B' / 'A and B' / 'A & B' to reach the first author
        idx = len(tokens) - 1
        cand = clean_surname(tokens[idx])
        if not valid_surname(cand):
            continue
        if idx >= 2 and tokens[idx - 1].lower() in CONJ_WORDS:
            prev = clean_surname(tokens[idx - 2])
            if valid_surname(prev):
                cand, idx = prev, idx - 2
        if idx >= 1 and tokens[idx - 1].lower() in ("de", "van", "von", "der", "da", "di", "du", "le", "la"):
            cand = tokens[idx - 1].lower() + " " + cand
        for y in years_of(m.group(1)):
            out.append((cand, y, m.start()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("verification_csv")
    ap.add_argument("--strict", action="store_true", help="treat uncited verified entries as errors")
    args = ap.parse_args()

    text = read_text(Path(args.report))
    cut = REF_HEADING.search(text)
    body = text[:cut.start()] if cut else text
    rows = read_csv(args.verification_csv)

    cites: list[tuple[str, str]] = []
    for m in PAREN.finditer(body):
        cites += parse_parenthetical(m.group(1))
    cites += [(s, y) for s, y, _ in parse_narrative(body)]

    entries = []
    for r in rows:
        status = (r.get("status") or "").strip().upper()
        fam = first_author_family(r.get("authors", ""))
        years = {str(to_int(r.get("year")) or ""), str(to_int(r.get("online_year")) or "")} - {""}
        entries.append((r, status, fam, years))

    no_entry, blocked_use, ambiguous = defaultdict(int), defaultdict(int), defaultdict(int)
    cited_ids: dict[int, int] = defaultdict(int)
    for surname, year in cites:
        y4, letter = year[:4], year[4:]
        hits = [e for e in entries if y4 in e[3] and surname_match(surname, e[2])]
        good = [e for e in hits if e[1] in PRINTABLE_STATUSES]
        if good:
            if len(good) > 1 and not letter:
                ambiguous[f"{surname} ({year})"] += 1
            target = good[ord(letter) - 97] if letter and ord(letter) - 97 < len(good) else good[0]
            cited_ids[id(target[0])] += 1
        elif any(e[1] in BLOCKED_STATUSES for e in hits):
            blocked_use[f"{surname} ({year})"] += 1
        else:
            no_entry[f"{surname} ({year})"] += 1

    link_problems, uncited = [], []
    for r, status, fam, years in entries:
        if status not in PRINTABLE_STATUSES:
            continue
        rid = r.get("ref_id") or f"{fam} {r.get('year', '')}"
        if not (norm_doi(r.get("doi", "")) or (r.get("link") or "").strip()):
            link_problems.append(f"{rid}: no DOI or link")
        elif not (r.get("link_check_method") or "").strip() or not (r.get("checked_on") or "").strip():
            link_problems.append(f"{rid}: link not checked (method/date missing)")
        if not cited_ids.get(id(r)):
            uncited.append(rid)

    printable = sum(1 for e in entries if e[1] in PRINTABLE_STATUSES)
    print(f"Citations found in text: {len(cites)} ({len(set(cites))} distinct)")
    print(f"Verification log: {len(entries)} rows, {printable} printable")

    def section(title, items):
        print(f"\n{title}: {len(items)}")
        for it in (sorted(items.items()) if isinstance(items, dict) else sorted(items)):
            print("  - " + (f"{it[0]}  x{it[1]}" if isinstance(it, tuple) else it))

    section("BLOCKING - cited but no entry in the verification log", no_entry)
    section("BLOCKING - cites a NOT_VERIFIED / RETRACTED source", blocked_use)
    section("BLOCKING - printable entry without a checked link", link_problems)
    section("CHECK - same author and year, add a/b suffix", ambiguous)
    section(("BLOCKING" if args.strict else "CHECK") + " - verified entry never cited", uncited)

    blocking = bool(no_entry or blocked_use or link_problems or (args.strict and uncited))
    print("\nRESULT: " + ("FAIL - fix the blocking items before delivery" if blocking else "PASS"))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
