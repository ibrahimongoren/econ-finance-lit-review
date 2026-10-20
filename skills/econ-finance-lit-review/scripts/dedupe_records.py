#!/usr/bin/env python3
"""Merge worker files, de-duplicate records and flag working-paper <-> journal pairs.

Usage:
    python3 scripts/dedupe_records.py litrev-<slug>/ [--title-threshold 0.93]

Reads 03_records.csv in the review folder. If parallel workers wrote
03_records_part*.csv files, their rows are first appended to 03_records.csv
(record_id must be unique across all files - prefix them per worker, e.g. A-001).

Writes:
    03_records_dedup.csv  unique records (one row per report; same-study pairs kept)
    03_duplicates.csv     record_id, duplicate_of, relation, basis, similarity

relation = "duplicate"   the same report found twice -> removed before screening
relation = "same-study"  a working paper/preprint and its journal version -> both kept
                         as reports of one study; cite the journal version and count
                         them as ONE study in synthesis and PRISMA.
Matching order: normalized DOI, then title similarity + first author + year (+-1).
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, WP_TYPES, first_author_family, norm_doi,  # noqa: E402
                           norm_surname, read_csv, surname_match, title_similarity,
                           to_int, write_csv)

DUP_HEADER = ["record_id", "duplicate_of", "relation", "basis", "similarity"]


def richness(row: dict) -> tuple:
    """Prefer the record with a DOI, a journal type, then more filled fields."""
    return (
        bool(norm_doi(row.get("doi", ""))),
        row.get("type", "") == "journal-article",
        sum(1 for v in row.values() if str(v or "").strip()),
    )


def dedupe(rows: list[dict], title_threshold: float = 0.93,
           pair_threshold: float = 0.85) -> tuple[list[dict], list[dict]]:
    """Return (unique_rows, duplicate_rows)."""
    canonical: dict[str, str] = {}      # record_id -> kept record_id
    dup_rows: list[dict] = []

    # 1) exact DOI duplicates
    by_doi: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        d = norm_doi(r.get("doi", ""))
        if d:
            by_doi[d].append(r)
    for d, group in by_doi.items():
        if len(group) < 2:
            continue
        keep = max(group, key=richness)
        for r in group:
            if r is not keep:
                canonical[r["record_id"]] = keep["record_id"]
                dup_rows.append({"record_id": r["record_id"], "duplicate_of": keep["record_id"],
                                 "relation": "duplicate", "basis": f"doi:{d}", "similarity": "1.00"})

    # 2) fuzzy duplicates and WP<->journal pairs, blocked by first-author surname
    remaining = [r for r in rows if r["record_id"] not in canonical]
    blocks: dict[str, list[dict]] = defaultdict(list)
    for r in remaining:
        key = norm_surname(first_author_family(r.get("authors", "")))
        blocks[key[:4] if key else "?"].append(r)

    paired: set[tuple[str, str]] = set()
    for block in blocks.values():
        for i, a in enumerate(block):
            if a["record_id"] in canonical:
                continue
            for b in block[i + 1:]:
                if b["record_id"] in canonical:
                    continue
                fa, fb = first_author_family(a.get("authors", "")), first_author_family(b.get("authors", ""))
                if fa and fb and not surname_match(fa, fb):
                    continue
                sim = title_similarity(a.get("title", ""), b.get("title", ""))
                ya, yb = to_int(a.get("year")), to_int(b.get("year"))
                year_close = ya is None or yb is None or abs(ya - yb) <= 1
                da, db = norm_doi(a.get("doi", "")), norm_doi(b.get("doi", ""))
                ta, tb = a.get("type", ""), b.get("type", "")
                wp_pair = (ta in WP_TYPES) != (tb in WP_TYPES)

                if wp_pair and sim >= pair_threshold:
                    journal, wp = (b, a) if ta in WP_TYPES else (a, b)
                    key = (wp["record_id"], journal["record_id"])
                    if key not in paired:
                        paired.add(key)
                        dup_rows.append({"record_id": wp["record_id"], "duplicate_of": journal["record_id"],
                                         "relation": "same-study", "basis": "title+author (WP<->journal)",
                                         "similarity": f"{sim:.2f}"})
                    continue
                if sim >= title_threshold and year_close and not (da and db and da != db):
                    keep, drop = (a, b) if richness(a) >= richness(b) else (b, a)
                    canonical[drop["record_id"]] = keep["record_id"]
                    dup_rows.append({"record_id": drop["record_id"], "duplicate_of": keep["record_id"],
                                     "relation": "duplicate", "basis": "title+author+year",
                                     "similarity": f"{sim:.2f}"})
                    if drop is a:
                        break

    unique = [r for r in rows if r["record_id"] not in canonical]
    return unique, dup_rows


def merge_parts(folder: Path) -> tuple[list[dict], list[str]]:
    main_path = folder / FILES["records"]
    rows = read_csv(main_path) if main_path.exists() else []
    merged_from = []
    seen = {r.get("record_id") for r in rows}
    for part in sorted(folder.glob("03_records_part*.csv")):
        added = 0
        for r in read_csv(part):
            if r.get("record_id") in seen:
                continue
            rows.append(r)
            seen.add(r.get("record_id"))
            added += 1
        merged_from.append(f"{part.name} (+{added})")
    if merged_from:
        header = HEADERS[FILES["records"]]
        extra = [k for r in rows for k in r if k not in header]
        write_csv(main_path, rows, header + sorted(set(extra)))
    return rows, merged_from


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="review folder (or a path to its 03_records.csv)")
    ap.add_argument("--title-threshold", type=float, default=0.93,
                    help="similarity for same-report duplicates (default 0.93)")
    ap.add_argument("--pair-threshold", type=float, default=0.85,
                    help="similarity for WP<->journal same-study pairs (default 0.85)")
    args = ap.parse_args()

    folder = Path(args.folder)
    if folder.is_file():
        folder = folder.parent
    rows, merged_from = merge_parts(folder)
    if not rows:
        print(f"No records found in {folder / FILES['records']}.")
        return 1
    missing = [r for r in rows if not r.get("record_id")]
    if missing:
        print(f"{len(missing)} row(s) lack record_id; fill them first.")
        return 1
    ids = [r["record_id"] for r in rows]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        print("record_id values must be unique; repeated: " + ", ".join(dupes[:10]))
        return 1

    unique, dup_rows = dedupe(rows, args.title_threshold, args.pair_threshold)
    header = list(rows[0].keys()) or HEADERS[FILES["records"]]
    write_csv(folder / FILES["records_dedup"], unique, header)
    write_csv(folder / FILES["duplicates"], dup_rows, DUP_HEADER)

    n_dup = sum(1 for d in dup_rows if d["relation"] == "duplicate")
    n_pair = sum(1 for d in dup_rows if d["relation"] == "same-study")
    if merged_from:
        print("Merged worker files: " + ", ".join(merged_from))
    print(f"Records in: {len(rows)}")
    print(f"Duplicates removed: {n_dup}")
    print(f"Unique records: {len(unique)}")
    print(f"WP<->journal same-study pairs flagged: {n_pair} (cite the journal version; count as one study)")
    print(f"Wrote {FILES['records_dedup']} and {FILES['duplicates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
