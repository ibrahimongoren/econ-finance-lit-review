#!/usr/bin/env python3
"""Figures for the visual report (PNG, 200 dpi) from the review's working files.

Usage:
    python3 scripts/make_figures.py litrev-<slug>/ [--lang tr|en] [--only years,map,weaknesses,regions,sources,pipeline]

Writes to 10_figures/:
  fig_years.png       included studies per publication year, stacked by method family (top 5 + other)
  fig_map.png         evidence map: theme x method family (counts, one-hue sequential scale)
  fig_weaknesses.png  weaknesses by category, stacked by severity (06_weaknesses.csv)
  fig_regions.png     included studies by country / region (top 12)
  fig_sources.png     records identified per source (search coverage)
  fig_pipeline.png    the review pipeline as a schema (stages 0-10)
The PRISMA flow comes from prisma_flow.py (04_prisma_flow.png). A figure whose data are missing is
skipped with a message. Colors follow a validated categorical palette in fixed order; one axis per
chart; every chart has direct labels or a legend and a table in the report, never color alone.
Requires matplotlib.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, PRINTABLE_STATUSES, SEVERITIES, WEAKNESS_CATEGORIES,  # noqa: E402
                           WEAKNESS_LABELS, read_csv, to_int)

SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#b9b8b1"
BLUE = {100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef", 300: "#6da7ec", 350: "#5598e7",
        400: "#3987e5", 450: "#2a78d6", 500: "#256abf", 550: "#1c5cab", 600: "#184f95", 650: "#104281",
        700: "#0d366b"}
SEV_COLOR = {"high": BLUE[650], "medium": BLUE[400], "low": BLUE[200]}

T = {
    "en": {"years": "Included studies by publication year and method", "year": "Publication year",
           "studies": "Studies", "map": "Evidence map: themes × methods", "weak": "Weaknesses across included studies",
           "count": "Weaknesses", "regions": "Included studies by country or region",
           "sources": "Records identified per source", "records": "Records", "other": "Other",
           "unclassified": "Unclassified", "sev": {"high": "High", "medium": "Medium", "low": "Low"},
           "pipeline": "Review pipeline", "no_theme": "(no theme)"},
    "tr": {"years": "Yayın yılına ve yönteme göre dahil edilen çalışmalar", "year": "Yayın yılı",
           "studies": "Çalışma", "map": "Kanıt haritası: temalar × yöntemler", "weak": "Dahil edilen çalışmalarda zayıf yönler",
           "count": "Zayıf yön", "regions": "Ülke veya bölgeye göre dahil edilen çalışmalar",
           "sources": "Kaynağa göre tanımlanan kayıtlar", "records": "Kayıt", "other": "Diğer",
           "unclassified": "Sınıflanmamış", "sev": {"high": "Yüksek", "medium": "Orta", "low": "Düşük"},
           "pipeline": "Tarama süreci", "no_theme": "(tema yok)"},
}
STAGES = {
    "en": ["0 Question &\nprotocol", "1 Prior reviews\n& seeds", "2 Search\nstrategy", "3 Search &\nidentification",
           "4 Screening\n& PRISMA", "5 Verification", "6 Three-pass\nreading cards", "7 Appraisal",
           "8 Synthesis &\nanswers", "9 Research\ngaps", "10 Report\n& audits"],
    "tr": ["0 Soru ve\nprotokol", "1 Önceki derlemeler\nve tohumlar", "2 Arama\nstratejisi", "3 Tarama ve\ntanımlama",
           "4 Eleme ve\nPRISMA", "5 Doğrulama", "6 Üç turlu\nokuma kartları", "7 Değerlendirme",
           "8 Sentez ve\ncevaplar", "9 Araştırma\nboşlukları", "10 Rapor ve\ndenetimler"],
}
PHASE = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 3]


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.titlecolor": INK, "axes.titlelocation": "left", "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    return plt


def _style_value_axis(ax, axis="y"):
    from matplotlib.ticker import MaxNLocator
    ax.grid(axis=axis, color=GRID, linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_locator(MaxNLocator(integer=True))
    ax.tick_params(length=0)


def _save(fig, out, plt):
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def included(folder: Path) -> tuple[list[dict], dict, dict]:
    """Studies with cards (window corpus) or, without cards, all printable verified studies."""
    ver = {r["ref_id"]: r for r in read_csv(folder / FILES["verification"])} \
        if (folder / FILES["verification"]).exists() else {}
    cards_path = folder / FILES["cards"]
    ids = [c["ref_id"] for c in read_csv(cards_path)] if cards_path.exists() else []
    if not ids:
        ids = [r for r, v in ver.items() if (v.get("status") or "").upper() in PRINTABLE_STATUSES]
    ext_path = folder / FILES["extraction"]
    ext = {r["ref_id"]: r for r in read_csv(ext_path)} if ext_path.exists() else {}
    return [ver[i] for i in ids if i in ver], ext, ver


def fig_years(folder, out, lang, plt):
    studies, ext, _ = included(folder)
    t = T[lang]
    rows = [(to_int(v.get("year")), (ext.get(v["ref_id"]) or {}).get("method_family") or t["unclassified"])
            for v in studies]
    rows = [(y, m) for y, m in rows if y]
    if not rows:
        return "no included studies with years"
    fam_counts = Counter(m for _, m in rows)
    top = [m for m, _ in fam_counts.most_common() if m != t["unclassified"]][:5]
    def fam(m): return m if m in top else (t["unclassified"] if m == t["unclassified"] else t["other"])
    order = top + [x for x in (t["other"], t["unclassified"]) if any(fam(m) == x for _, m in rows)]
    years = list(range(min(y for y, _ in rows), max(y for y, _ in rows) + 1))
    data = {f: [sum(1 for y, m in rows if y == yr and fam(m) == f) for yr in years] for f in order}
    fig, ax = plt.subplots(figsize=(7.5, 3.9))
    bottom = [0] * len(years)
    for i, f in enumerate(order):
        color = CATEGORICAL[i] if f in top else OTHER
        ax.bar(years, data[f], bottom=bottom, color=color, width=0.62, edgecolor=SURFACE, linewidth=1.5, label=f)
        bottom = [b + v for b, v in zip(bottom, data[f])]
    for x, total in zip(years, bottom):
        if total:
            ax.text(x, total + max(bottom) * 0.015, str(total), ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_ylim(0, max(bottom) * 1.15)
    ax.set_xticks(years)
    ax.set_xlabel(t["year"])
    ax.set_ylabel(t["studies"])
    ax.set_title(t["years"])
    _style_value_axis(ax, "y")
    ax.legend(ncol=min(4, len(order)), fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.18))
    fig.tight_layout()
    _save(fig, out, plt)


def fig_map(folder, out, lang, plt):
    studies, ext, _ = included(folder)
    t = T[lang]
    cards_path = folder / FILES["cards"]
    card_theme = {c["ref_id"]: c.get("theme", "") for c in read_csv(cards_path)} if cards_path.exists() else {}
    pairs = []
    for v in studies:
        e = ext.get(v["ref_id"]) or {}
        theme = card_theme.get(v["ref_id"]) or e.get("theme") or t["no_theme"]
        method = e.get("method_family") or t["unclassified"]
        pairs.append((theme, method))
    if not pairs or all(m == t["unclassified"] for _, m in pairs):
        return "no themes/methods coded in 06_extraction.csv"
    themes = [th for th, _ in Counter(p[0] for p in pairs).most_common(10)]
    methods = [m for m, _ in Counter(p[1] for p in pairs).most_common(8)]
    grid = [[sum(1 for th, m in pairs if th == r and m == c) for c in methods] for r in themes]
    vmax = max(max(row) for row in grid) or 1
    steps = [BLUE[s] for s in (100, 200, 300, 400, 500, 600, 700)]
    fig_h = 1.0 + 0.42 * len(themes)
    fig, ax = plt.subplots(figsize=(7.5, max(2.6, fig_h)))
    for i, row in enumerate(grid):
        for j, val in enumerate(row):
            color = SURFACE if val == 0 else steps[min(len(steps) - 1, int(round((val / vmax) * (len(steps) - 1))))]
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=color, ec=GRID if val == 0 else color, lw=0.6))
            if val:
                light = color in steps[:3]
                ax.text(j + 0.48, i + 0.46, str(val), ha="center", va="center", fontsize=9,
                        color=INK if light else "#ffffff", fontweight="bold")
    ax.set_xlim(0, len(methods))
    ax.set_ylim(len(themes), 0)
    ax.set_xticks([j + 0.48 for j in range(len(methods))])
    ax.set_xticklabels([m if len(m) <= 18 else m[:17] + "…" for m in methods], rotation=30, ha="right", fontsize=8)
    ax.set_yticks([i + 0.46 for i in range(len(themes))])
    ax.set_yticklabels([th if len(th) <= 32 else th[:31] + "…" for th in themes], fontsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(t["map"])
    fig.tight_layout()
    _save(fig, out, plt)


def fig_weaknesses(folder, out, lang, plt):
    path = folder / FILES["weaknesses"]
    rows = read_csv(path) if path.exists() else []
    if not rows:
        return "06_weaknesses.csv is empty"
    t = T[lang]
    counts = defaultdict(Counter)
    for w in rows:
        if w.get("category") in WEAKNESS_CATEGORIES:
            counts[w["category"]][(w.get("severity") or "").lower()] += 1
    cats = sorted(counts, key=lambda c: sum(counts[c].values()))
    fig, ax = plt.subplots(figsize=(7.5, 0.9 + 0.38 * len(cats)))
    left = [0] * len(cats)
    labels = [WEAKNESS_LABELS[lang][c] for c in cats]
    for sev in SEVERITIES:
        vals = [counts[c].get(sev, 0) for c in cats]
        ax.barh(labels, vals, left=left, color=SEV_COLOR[sev], height=0.6, edgecolor=SURFACE, linewidth=1.5,
                label=t["sev"][sev])
        left = [a + b for a, b in zip(left, vals)]
    for i, total in enumerate(left):
        ax.text(total + max(left) * 0.01, i, str(total), va="center", fontsize=8, color=INK2)
    ax.set_xlabel(t["count"])
    ax.set_title(t["weak"])
    _style_value_axis(ax, "x")
    fig.tight_layout()
    handles, labels_ = ax.get_legend_handles_labels()
    fig.legend(handles, labels_, ncol=3, fontsize=8, loc="upper left", bbox_to_anchor=(0.0, 0.0),
               handlelength=1.2)
    _save(fig, out, plt)


def _single_bar(labels_counts, title, xlabel, out, plt):
    labels = [k for k, _ in labels_counts][::-1]
    vals = [v for _, v in labels_counts][::-1]
    fig, ax = plt.subplots(figsize=(7.5, 0.9 + 0.33 * len(labels)))
    ax.barh(labels, vals, color=CATEGORICAL[0], height=0.6)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, i, str(v), va="center", fontsize=8, color=INK2)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    _style_value_axis(ax, "x")
    fig.tight_layout()
    _save(fig, out, plt)


def fig_regions(folder, out, lang, plt):
    studies, ext, _ = included(folder)
    c = Counter()
    for v in studies:
        val = (ext.get(v["ref_id"]) or {}).get("country_region", "")
        for part in [p.strip() for p in val.replace(";", ",").split(",") if p.strip()]:
            c[part] += 1
    if not c:
        return "no country_region coded in 06_extraction.csv"
    _single_bar(c.most_common(12), T[lang]["regions"], T[lang]["studies"], out, plt)


SOURCE_LABELS = {"semanticscholar": "Semantic Scholar", "webofscience": "Web of Science", "openalex": "OpenAlex",
                 "googlescholar-serpapi": "Google Scholar (SerpApi)", "sciencedirect": "ScienceDirect",
                 "publishorperish": "Publish or Perish", "arxiv": "arXiv", "crossref": "Crossref", "scopus": "Scopus"}
SNOWBALL = {"en": {"backward": "Snowballing (backward)", "forward": "Snowballing (forward)", "": "Snowballing"},
            "tr": {"backward": "Kartopu (geriye)", "forward": "Kartopu (ileriye)", "": "Kartopu taraması"}}


def source_label(raw: str, lang: str) -> str:
    key = "".join((raw or "").lower().split())
    if key.startswith("snowball"):
        direction = "backward" if "back" in key else ("forward" if "forw" in key else "")
        return SNOWBALL[lang][direction]
    return SOURCE_LABELS.get(key, raw or "unknown")


def fig_sources(folder, out, lang, plt):
    rec = folder / FILES["records"]
    rows = read_csv(rec) if rec.exists() else []
    if not rows:
        return "03_records.csv is empty"
    c = Counter(source_label(r.get("source") or "unknown", lang) for r in rows)
    _single_bar(c.most_common(12), T[lang]["sources"], T[lang]["records"], out, plt)


def fig_pipeline(folder, out, lang, plt):
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    labels = STAGES[lang]
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 2.25)
    ax.axis("off")
    pos = [(i, 1.35) for i in range(6)] + [(5 - i, 0.15) for i in range(5)]
    for k, ((x, y), text) in enumerate(zip(pos, labels)):
        color = CATEGORICAL[PHASE[k]]
        ax.add_patch(FancyBboxPatch((x + 0.06, y), 0.86, 0.72, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    fc=SURFACE, ec=color, lw=1.6))
        ax.add_patch(FancyBboxPatch((x + 0.06, y + 0.62), 0.86, 0.10, boxstyle="square,pad=0", fc=color, ec=color))
        ax.text(x + 0.49, y + 0.30, text, ha="center", va="center", fontsize=7.2, color=INK)
    for k in range(len(pos) - 1):
        (x0, y0), (x1, y1) = pos[k], pos[k + 1]
        if y0 == y1:
            start = (x0 + 0.92, y0 + 0.36) if x1 > x0 else (x0 + 0.06, y0 + 0.36)
            end = (x1 + 0.06, y1 + 0.36) if x1 > x0 else (x1 + 0.92, y1 + 0.36)
        else:
            start, end = (x0 + 0.49, y0), (x1 + 0.49, y1 + 0.72)
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9, color=MUTED, lw=1))
    ax.set_title(T[lang]["pipeline"])
    fig.tight_layout()
    _save(fig, out, plt)


FIGURES = {"years": fig_years, "map": fig_map, "weaknesses": fig_weaknesses, "regions": fig_regions,
           "sources": fig_sources, "pipeline": fig_pipeline}


def make(folder: Path, lang: str = "en", only: list[str] | None = None) -> dict:
    try:
        plt = _plt()
    except ImportError:
        print("matplotlib is not installed - figures skipped")
        return {}
    outdir = folder / FILES["figures_dir"]
    outdir.mkdir(exist_ok=True)
    made = {}
    for name, fn in FIGURES.items():
        if only and name not in only:
            continue
        out = outdir / f"fig_{name}.png"
        msg = fn(folder, out, lang, plt)
        if msg:
            print(f"  · fig_{name}: skipped ({msg})")
        else:
            made[name] = out
            print(f"  ✓ {out}")
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--lang", choices=["tr", "en"], default="en")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    made = make(Path(a.folder), a.lang, [x.strip() for x in a.only.split(",") if x.strip()] or None)
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
