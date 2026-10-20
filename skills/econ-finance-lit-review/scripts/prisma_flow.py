#!/usr/bin/env python3
"""PRISMA 2020 counts and flow diagram from the review folder.

Usage:
    python3 scripts/prisma_flow.py litrev-<slug>/ [--lang en|tr] [--no-figure]

Reads 03_records.csv, 03_duplicates.csv (if present, from dedupe_records.py) and
04_screening.csv. Writes 04_prisma_counts.json and, if matplotlib is available,
04_prisma_flow.png and 04_prisma_flow.svg.

04_screening.csv conventions
    stage    : ta (title/abstract) | ft (full text)
    decision : include | exclude | maybe | not_retrieved
    reason_code : exclusion code from the protocol (E1, E2, ...)
A record with a ta 'include' and no ft row is counted as included at abstract
level (rapid mode) and reported separately. A ta 'exclude' with reason E7 (outside the
publication window, e.g. from screening_check.py window) is reported as removed before
screening, next to the duplicates, as PRISMA 2020 asks for records removed by automation. The diagram uses a single column with
the identification box split into databases/registers and other methods.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import FILES, is_other_method, read_csv  # noqa: E402

LABELS = {
    "tr": {
        "ident": "Tanımlanan kayıtlar (n = {total})\nVeri tabanları/dizinler: {db}\nDiğer yöntemler (kartopu, yazar, tohum): {other}",
        "dups": "Elemeden önce çıkarılan kayıtlar\nMükerrer: n = {n}\nYayın penceresi dışında (E7): n = {w}",
        "screened": "Taranan kayıtlar\n(başlık/özet) (n = {n})",
        "ta_excl": "Dışlanan kayıtlar (n = {n})",
        "sought": "Tam metni aranan raporlar (n = {n})",
        "not_retr": "Erişilemeyen raporlar (n = {n})",
        "assessed": "Uygunluk açısından\ndeğerlendirilen raporlar (n = {n})",
        "ft_excl": "Dışlanan raporlar (n = {n})\n{reasons}",
        "included": "Dahil edilen çalışmalar (n = {studies})\nDahil edilen raporlar (n = {reports})",
        "abs_note": "Yalnızca özet düzeyinde dahil: {n}",
        "phase": ["Tanımlama", "Tarama", "Dahil etme"],
        "title": "PRISMA 2020 akış diyagramı",
    },
    "en": {
        "ident": "Records identified (n = {total})\nDatabases/indexes: {db}\nOther methods (snowballing, authors, seeds): {other}",
        "dups": "Records removed before screening\nDuplicates: n = {n}\nOutside the publication window (E7): n = {w}",
        "screened": "Records screened\n(title/abstract) (n = {n})",
        "ta_excl": "Records excluded (n = {n})",
        "sought": "Reports sought for retrieval (n = {n})",
        "not_retr": "Reports not retrieved (n = {n})",
        "assessed": "Reports assessed\nfor eligibility (n = {n})",
        "ft_excl": "Reports excluded (n = {n})\n{reasons}",
        "included": "Studies included (n = {studies})\nReports of included studies (n = {reports})",
        "abs_note": "Included at abstract level only: {n}",
        "phase": ["Identification", "Screening", "Included"],
        "title": "PRISMA 2020 flow diagram",
    },
}


def last_decision(rows: list[dict], stage: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        if (r.get("stage") or "").strip().lower() == stage:
            out[r["record_id"]] = r
    return out


def compute(folder: Path) -> OrderedDict:
    records = read_csv(folder / FILES["records"])
    dups_path = folder / FILES["duplicates"]
    dup_rows = read_csv(dups_path) if dups_path.exists() else []
    screening_path = folder / FILES["screening"]
    screening = read_csv(screening_path) if screening_path.exists() else []

    removed = {d["record_id"] for d in dup_rows if d.get("relation") == "duplicate"}
    pairs = [(d["record_id"], d["duplicate_of"]) for d in dup_rows if d.get("relation") == "same-study"]
    unique_ids = [r["record_id"] for r in records if r["record_id"] not in removed]

    by_source = Counter((r.get("source") or "unknown").strip() for r in records)
    n_other = sum(1 for r in records if is_other_method(r.get("source", "")))

    ta = last_decision(screening, "ta")
    ft = last_decision(screening, "ft")
    norm = lambda row: (row.get("decision") or "").strip().lower()  # noqa: E731

    window_removed = {i for i in unique_ids if i in ta and norm(ta[i]) == "exclude"
                      and (ta[i].get("reason_code") or "").strip().upper() == "E7"}
    screened = [i for i in unique_ids if i in ta and i not in window_removed]
    not_screened = [i for i in unique_ids if i not in ta]
    ta_excluded = [i for i in screened if norm(ta[i]) == "exclude"]
    passed = [i for i in screened if norm(ta[i]) in ("include", "maybe")]
    sought = [i for i in passed if i in ft]
    pending = [i for i in passed if i not in ft and norm(ta[i]) == "maybe"]
    abstract_only = [i for i in passed if i not in ft and norm(ta[i]) == "include"]
    not_retrieved = [i for i in sought if norm(ft[i]) == "not_retrieved"]
    assessed = [i for i in sought if norm(ft[i]) in ("include", "exclude")]
    ft_excluded = [i for i in assessed if norm(ft[i]) == "exclude"]
    ft_included = [i for i in assessed if norm(ft[i]) == "include"]
    reasons = Counter((ft[i].get("reason_code") or "unspecified").strip() for i in ft_excluded)

    included_reports = set(ft_included) | set(abstract_only)
    linked = sum(1 for a, b in pairs if a in included_reports and b in included_reports)

    counts = OrderedDict(
        identified_total=len(records),
        identified_databases=len(records) - n_other,
        identified_other_methods=n_other,
        identified_by_source=dict(by_source.most_common()),
        duplicates_removed=len(removed),
        removed_outside_window=len(window_removed),
        records_screened=len(screened),
        records_not_yet_screened=len(not_screened),
        records_excluded_title_abstract=len(ta_excluded),
        reports_sought=len(sought),
        reports_not_retrieved=len(not_retrieved),
        reports_assessed=len(assessed),
        reports_excluded_full_text=len(ft_excluded),
        exclusion_reasons=dict(sorted(reasons.items())),
        reports_included=len(included_reports),
        included_abstract_level_only=len(abstract_only),
        studies_included=len(included_reports) - linked,
        same_study_pairs_among_included=linked,
        pending_maybe_without_full_text=len(pending),
    )
    return counts


def warnings(c: OrderedDict) -> list[str]:
    w = []
    if c["records_not_yet_screened"]:
        w.append(f"{c['records_not_yet_screened']} unique record(s) have no title/abstract decision yet.")
    if c["pending_maybe_without_full_text"]:
        w.append(f"{c['pending_maybe_without_full_text']} 'maybe' record(s) still need a full-text decision.")
    if c["included_abstract_level_only"]:
        w.append(f"{c['included_abstract_level_only']} record(s) included at abstract level only - label them [AB] (abstract only).")
    return w


def draw(c: OrderedDict, folder: Path, lang: str) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        print("matplotlib not available - figure skipped (counts JSON still written).")
        return []

    L = LABELS.get(lang.lower()[:2], LABELS["en"])
    reasons = "\n".join(f"{k}: {v}" for k, v in c["exclusion_reasons"].items()) or "-"
    fig, ax = plt.subplots(figsize=(10, 11))
    ax.set_xlim(0, 100)
    ax.set_ylim(14, 110)
    ax.axis("off")

    def box(x, y, w, h, text, face="#ffffff"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    linewidth=1.1, edgecolor="#333333", facecolor=face))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9, wrap=True)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.1))

    main_x, main_w, side_x, side_w, h = 14, 42, 64, 33, 9
    ys = [93, 75, 59, 43, 22]
    box(main_x, ys[0], main_w, h + 3, L["ident"].format(
        total=c["identified_total"], db=c["identified_databases"], other=c["identified_other_methods"]))
    box(side_x, ys[0], side_w, h + 3, L["dups"].format(n=c["duplicates_removed"],
                                                       w=c.get("removed_outside_window", 0)))
    box(main_x, ys[1], main_w, h, L["screened"].format(n=c["records_screened"]))
    box(side_x, ys[1], side_w, h, L["ta_excl"].format(n=c["records_excluded_title_abstract"]))
    box(main_x, ys[2], main_w, h, L["sought"].format(n=c["reports_sought"]))
    box(side_x, ys[2], side_w, h, L["not_retr"].format(n=c["reports_not_retrieved"]))
    box(main_x, ys[3], main_w, h, L["assessed"].format(n=c["reports_assessed"]))
    n_reason_lines = max(1, len(c["exclusion_reasons"]))
    ex_h = h + 2.2 * n_reason_lines
    box(side_x, ys[3] + h - ex_h, side_w, ex_h, L["ft_excl"].format(n=c["reports_excluded_full_text"], reasons=reasons))
    inc = L["included"].format(studies=c["studies_included"], reports=c["reports_included"])
    if c["included_abstract_level_only"]:
        inc += "\n" + L["abs_note"].format(n=c["included_abstract_level_only"])
    box(main_x, ys[4], main_w, h + 3, inc, face="#eef4fb")

    cx = main_x + main_w / 2
    arrow(cx, ys[0], cx, ys[1] + h)
    arrow(cx, ys[1], cx, ys[2] + h)
    arrow(cx, ys[2], cx, ys[3] + h)
    arrow(cx, ys[3], cx, ys[4] + h + 3)
    for y in (ys[0] + (h + 3) / 2, ys[1] + h / 2, ys[2] + h / 2, ys[3] + h / 2):
        arrow(main_x + main_w, y, side_x, y)

    for label, (y0, y1) in zip(L["phase"], [(88, 107), (38, 86), (20, 36)]):
        ax.add_patch(FancyBboxPatch((1, y0), 8, y1 - y0, boxstyle="round,pad=0.2,rounding_size=1",
                                    linewidth=0, facecolor="#dbe6f3"))
        ax.text(5, (y0 + y1) / 2, label, rotation=90, ha="center", va="center", fontsize=10, weight="bold")
    ax.set_title(L["title"], fontsize=12, weight="bold")

    paths = [folder / "04_prisma_flow.png", folder / "04_prisma_flow.svg"]
    fig.savefig(paths[0], dpi=200, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--lang", default="en", help="label language: en or tr (others fall back to en)")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args(argv)

    folder = Path(args.folder)
    if not (folder / FILES["records"]).exists():
        print(f"{FILES['records']} not found in {folder}")
        return 1
    counts = compute(folder)
    (folder / FILES["prisma_counts"]).write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in counts.items():
        print(f"{k}: {v}")
    for w in warnings(counts):
        print("WARNING: " + w)
    if not args.no_figure:
        for p in draw(counts, folder, args.lang):
            print(f"Wrote {p}")
    print(f"Wrote {folder / FILES['prisma_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
