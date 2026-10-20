#!/usr/bin/env python3
"""Screening helpers: literature-window exclusions (E7) and a blind re-screen of a sample + Cohen's kappa.

A review screened by one reviewer has no inter-rater check. This script supplies
the closest substitute: a stratified random sample is re-screened blind (ideally by
a separate agent that has not seen the first decisions), then the two sets of
decisions are compared.

Usage:
    python3 scripts/screening_check.py window  litrev-<slug>/ [--window 2021-2026] [--dry-run]
    python3 scripts/screening_check.py sample  litrev-<slug>/ [--n 40] [--seed 7] [--stage ta]
    python3 scripts/screening_check.py compare litrev-<slug>/ [--stage ta] [--min-kappa 0.6]

window   applies the literature window before title/abstract screening: every de-duplicated record
         whose publication year lies outside the window (from --window, else 00_protocol.md, else the
         last five years) and that has no 'ta' decision yet gets "exclude, E7" in 04_screening.csv.
         Records without a readable year are listed for a manual decision, never excluded. Online-first
         articles straddling the boundary can be re-included by editing the decision (note why).

sample   writes 04_rescreen.csv: record_id, title, abstract, decision (empty),
         reason_code (empty). The first decisions are NOT included - the
         re-screener must work from the protocol criteria alone. About half the
         sample comes from records first judged include/maybe, half from excludes,
         so a low-prevalence set still tests both kinds of decision.
compare  reads the filled 04_rescreen.csv and 04_screening.csv, treats
         include/maybe as "in" and exclude as "out", and reports agreement,
         Cohen's kappa and every disagreement. Exit code 1 if kappa < --min-kappa.
Because the sample is stratified, kappa describes consistency on this test set,
not a population estimate; report it as such.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, in_window, parse_window, read_csv,  # noqa: E402
                           window_from_protocol, write_csv)

RESCREEN_HEADER = ["record_id", "title", "abstract", "decision", "reason_code", "note"]


def binarise(decision: str) -> str | None:
    d = (decision or "").strip().lower()
    if d in ("include", "maybe"):
        return "in"
    if d == "exclude":
        return "out"
    return None


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """Return (observed agreement, kappa) for two binary raters."""
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    pa_in = sum(1 for a, _ in pairs if a == "in") / n
    pb_in = sum(1 for _, b in pairs if b == "in") / n
    pe = pa_in * pb_in + (1 - pa_in) * (1 - pb_in)
    if pe >= 1.0:
        return po, 1.0 if po == 1.0 else 0.0
    return po, (po - pe) / (1 - pe)


def decisions(screening: list[dict], stage: str) -> dict[str, str]:
    out = {}
    for r in screening:
        if (r.get("stage") or "").strip().lower() == stage:
            out[r.get("record_id")] = r.get("decision", "")
    return out


def cmd_window(folder: Path, window_arg: str, dry_run: bool) -> int:
    window = parse_window(window_arg) if window_arg else (window_from_protocol(folder) or parse_window(""))
    rec_path = folder / FILES["records_dedup"]
    if not rec_path.exists():
        rec_path = folder / FILES["records"]
        print(f"Note: {FILES['records_dedup']} not found - using {FILES['records']} (run dedupe_records.py first)")
    records = read_csv(rec_path)
    scr_path = folder / FILES["screening"]
    screening = read_csv(scr_path) if scr_path.exists() else []
    decided = set(decisions(screening, "ta"))
    new, unknown, inside = [], [], 0
    for r in records:
        status = in_window(r.get("year"), window)
        if status is None:
            unknown.append(r)
        elif status:
            inside += 1
        elif r["record_id"] not in decided:
            new.append({"record_id": r["record_id"], "stage": "ta", "decision": "exclude", "reason_code": "E7",
                        "note": f"year {r.get('year')} outside window {window[0]}-{window[1]} (automatic)"})
    print(f"Window {window[0]}-{window[1]} · records: {len(records)} · inside: {inside} · "
          f"outside (new E7): {len(new)} · year unknown: {len(unknown)}")
    for r in unknown[:30]:
        print(f"  year unknown - decide by hand: {r['record_id']} | {(r.get('title') or '')[:70]}")
    if len(unknown) > 30:
        print(f"  ... and {len(unknown) - 30} more")
    if dry_run:
        print("Dry run - nothing written.")
        return 0
    if new:
        write_csv(scr_path, screening + new, HEADERS[FILES["screening"]])
        print(f"Appended {len(new)} E7 exclusion(s) to {scr_path}")
    return 0


def cmd_sample(folder: Path, n: int, seed: int, stage: str) -> int:
    rec_path = folder / FILES["records_dedup"]
    if not rec_path.exists():
        rec_path = folder / FILES["records"]
    records = {r["record_id"]: r for r in read_csv(rec_path)}
    first = decisions(read_csv(folder / FILES["screening"]), stage)
    ins = sorted(i for i, d in first.items() if binarise(d) == "in" and i in records)
    outs = sorted(i for i, d in first.items() if binarise(d) == "out" and i in records)
    if not ins and not outs:
        print(f"No '{stage}' decisions found in {FILES['screening']}.")
        return 1
    rng = random.Random(seed)
    k_in = min(len(ins), max(n // 2, n - len(outs)))
    k_out = min(len(outs), n - k_in)
    chosen = rng.sample(ins, k_in) + rng.sample(outs, k_out)
    rng.shuffle(chosen)
    rows = [{"record_id": i, "title": records[i].get("title", ""),
             "abstract": records[i].get("abstract", "")} for i in chosen]
    out = folder / FILES["rescreen"]
    write_csv(out, rows, RESCREEN_HEADER)
    print(f"Wrote {out} with {len(rows)} records ({k_in} first judged in, {k_out} out; seed {seed}).")
    print("Re-screen them blind against the protocol criteria, fill 'decision' "
          "(include / exclude / maybe) and 'reason_code', then run: compare")
    return 0


def cmd_compare(folder: Path, stage: str, min_kappa: float) -> int:
    first = decisions(read_csv(folder / FILES["screening"]), stage)
    second = read_csv(folder / FILES["rescreen"])
    pairs, disagreements, blank = [], [], 0
    for r in second:
        b = binarise(r.get("decision", ""))
        a = binarise(first.get(r.get("record_id"), ""))
        if b is None:
            blank += 1
            continue
        if a is None:
            continue
        pairs.append((a, b))
        if a != b:
            disagreements.append((r.get("record_id"), first.get(r.get("record_id")), r.get("decision"),
                                  r.get("title", "")[:70]))
    po, kappa = cohen_kappa(pairs)
    print(f"Compared: {len(pairs)} · blank re-screen decisions: {blank}")
    print(f"Observed agreement: {po:.1%} · Cohen's kappa: {kappa:.2f}")
    if disagreements:
        print("\nDisagreements (record_id | first | second | title):")
        for d in disagreements:
            print(f"  {d[0]} | {d[1]} | {d[2]} | {d[3]}")
    ok = len(pairs) > 0 and kappa >= min_kappa
    print("\nRESULT: " + ("PASS" if ok else
                          f"FAIL - kappa below {min_kappa}: clarify the criteria behind the disagreements, "
                          "re-screen the affected records and record the change in 00_protocol.md"))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("window")
    w.add_argument("folder")
    w.add_argument("--window", default="")
    w.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("sample")
    s.add_argument("folder")
    s.add_argument("--n", type=int, default=40)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--stage", choices=["ta", "ft"], default="ta")
    c = sub.add_parser("compare")
    c.add_argument("folder")
    c.add_argument("--stage", choices=["ta", "ft"], default="ta")
    c.add_argument("--min-kappa", type=float, default=0.6)
    args = ap.parse_args(argv)
    folder = Path(args.folder)
    if args.cmd == "window":
        return cmd_window(folder, args.window, args.dry_run)
    if args.cmd == "sample":
        return cmd_sample(folder, args.n, args.seed, args.stage)
    return cmd_compare(folder, args.stage, args.min_kappa)


if __name__ == "__main__":
    sys.exit(main())
