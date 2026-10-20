#!/usr/bin/env python3
"""Coverage and saturation check for a comprehensive search.

Usage:
    python3 scripts/coverage_check.py litrev-<slug>/ [--window 3] [--threshold 0.05]

Answers two questions that decide whether searching can stop:
  1. Seed recall - did the searches retrieve every seed paper in 01_seeds.csv?
     (seeds are the known, verified core papers; a missed seed means the search
     strings or sources are incomplete)
  2. Saturation - did the last N queries / snowball rounds in 02_search_log.csv
     still add new unique records and, once screening has started, new included
     studies?

Reads 01_seeds.csv, 02_search_log.csv, 03_records.csv and, when present,
03_duplicates.csv and 04_screening.csv. Writes 03_coverage.md. Log snowball rounds
in the search log too (query_id S1, S2 ... with source 'snowball-backward' or
'snowball-forward'), so they count in the saturation sequence.
Exit code 0 when both checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import FILES, find_record, read_csv  # noqa: E402


def load(folder: Path, key: str) -> list[dict]:
    path = folder / FILES[key]
    return read_csv(path) if path.exists() else []


def included_ids(screening: list[dict]) -> set[str]:
    """Record ids currently included: full-text include, or abstract include with no ft row."""
    ta, ft = {}, {}
    for r in screening:
        stage = (r.get("stage") or "").strip().lower()
        (ta if stage == "ta" else ft if stage == "ft" else {})[r.get("record_id")] = \
            (r.get("decision") or "").strip().lower()
    inc = {i for i, d in ft.items() if d == "include"}
    inc |= {i for i, d in ta.items() if d == "include" and i not in ft}
    return inc


def analyze(folder: Path, window: int = 3, threshold: float = 0.05) -> dict:
    seeds = load(folder, "seeds")
    log = load(folder, "search_log")
    records = load(folder, "records")
    dups = load(folder, "duplicates")
    screening = load(folder, "screening")

    # --- seed recall -------------------------------------------------------
    seed_rows = []
    for s in seeds:
        hit = find_record(records, s.get("title", ""), s.get("doi", ""), s.get("authors", ""), s.get("year"))
        seed_rows.append({"seed_id": s.get("seed_id", ""), "title": s.get("title", ""),
                          "found": bool(hit), "record_id": hit.get("record_id", "") if hit else "",
                          "query_id": hit.get("query_id", "") if hit else ""})
    found = sum(1 for r in seed_rows if r["found"])

    # --- saturation --------------------------------------------------------
    canon = {d["record_id"]: d["duplicate_of"] for d in dups if d.get("relation") == "duplicate"}
    pair = {d["record_id"]: d["duplicate_of"] for d in dups if d.get("relation") == "same-study"}

    def study_of(rid: str) -> str:
        rid = canon.get(rid, rid)
        return pair.get(rid, rid)

    inc_studies = {study_of(i) for i in included_ids(screening)}
    screened = bool(screening)

    order = [q.get("query_id", "") for q in log if q.get("query_id")]
    meta = {q.get("query_id"): q for q in log}
    for r in records:
        q = r.get("query_id", "")
        if q and q not in order:
            order.append(q)

    seen, seen_inc, rows = set(), set(), []
    for q in order:
        recs = [r for r in records if r.get("query_id") == q]
        studies = {study_of(r["record_id"]) for r in recs if r.get("record_id")}
        new = studies - seen
        new_inc = (new & inc_studies) - seen_inc if screened else set()
        seen |= studies
        seen_inc |= studies & inc_studies
        rows.append({"query_id": q, "source": (meta.get(q) or {}).get("source", "(not in search log)"),
                     "retrieved": (meta.get(q) or {}).get("retrieved", ""), "records": len(recs),
                     "new_unique": len(new), "new_included": len(new_inc) if screened else "",
                     "cum_unique": len(seen), "cum_included": len(seen_inc) if screened else ""})

    tail = rows[-window:] if len(rows) >= window else rows
    tail_new = sum(r["new_unique"] for r in tail)
    share_unique = tail_new / len(seen) if seen else 1.0
    if screened and seen_inc:
        tail_inc = sum(r["new_included"] for r in tail)
        share_inc = tail_inc / len(seen_inc)
    else:
        tail_inc, share_inc = None, None
    basis = share_inc if share_inc is not None else share_unique
    saturated = len(rows) >= window and basis < threshold
    unlogged = [r["query_id"] for r in rows if r["source"] == "(not in search log)"]

    return {"seeds": seed_rows, "seed_found": found, "seed_total": len(seeds), "rows": rows,
            "window": window, "threshold": threshold, "share_unique": share_unique,
            "share_included": share_inc, "tail_new": tail_new, "tail_inc": tail_inc,
            "saturated": saturated, "screened": screened, "unlogged": unlogged}


def report(res: dict) -> str:
    lines = ["# Coverage and saturation check", ""]
    st = res["seed_total"]
    lines.append(f"## Seed recall: {res['seed_found']}/{st}" + ("" if st else " (no seeds listed - add 01_seeds.csv)"))
    lines.append("")
    if st:
        lines += ["| Seed | Found | Record | Query | Title |", "|---|---|---|---|---|"]
        for s in res["seeds"]:
            lines.append(f"| {s['seed_id']} | {'yes' if s['found'] else '**NO**'} | {s['record_id']} | "
                         f"{s['query_id']} | {s['title'][:80]} |")
        lines.append("")
    lines += [f"## Saturation (last {res['window']} queries/rounds)", "",
              "| Query | Source | Retrieved | Records | New unique | New included | Cum. unique | Cum. included |",
              "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['query_id']} | {r['source']} | {r['retrieved']} | {r['records']} | {r['new_unique']} | "
                     f"{r['new_included']} | {r['cum_unique']} | {r['cum_included']} |")
    lines.append("")
    if res["share_included"] is not None:
        lines.append(f"New included studies in the last {res['window']}: {res['tail_inc']} "
                     f"({res['share_included']:.1%} of included).")
    lines.append(f"New unique records in the last {res['window']}: {res['tail_new']} "
                 f"({res['share_unique']:.1%} of unique).")
    lines.append(f"Threshold: {res['threshold']:.0%} · Basis: "
                 f"{'included studies' if res['share_included'] is not None else 'unique records (screening not started)'}")
    lines.append("")
    seeds_ok = res["seed_total"] > 0 and res["seed_found"] == res["seed_total"]
    lines.append("## Verdict")
    lines.append(f"- Seed recall: {'PASS' if seeds_ok else 'FAIL - fix strings/sources or explain each miss'}")
    lines.append(f"- Saturation: {'PASS' if res['saturated'] else 'NOT YET - run more queries or snowball rounds'}")
    if res["unlogged"]:
        lines.append(f"- Query ids used in records but missing from the search log: {', '.join(res['unlogged'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--window", type=int, default=3, help="number of most recent queries/rounds (default 3)")
    ap.add_argument("--threshold", type=float, default=0.05, help="max share of new items in the window (default 0.05)")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not (folder / FILES["records"]).exists():
        print(f"{FILES['records']} not found in {folder}")
        return 1
    res = analyze(folder, args.window, args.threshold)
    text = report(res)
    (folder / "03_coverage.md").write_text(text, encoding="utf-8")
    print(text)
    seeds_ok = res["seed_total"] > 0 and res["seed_found"] == res["seed_total"]
    return 0 if (seeds_ok and res["saturated"]) else 1


if __name__ == "__main__":
    sys.exit(main())
