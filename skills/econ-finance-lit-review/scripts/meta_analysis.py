#!/usr/bin/env python3
"""Meta-analysis and publication-bias diagnostics for comparable estimates.

Usage:
    python3 scripts/meta_analysis.py litrev-<slug>/ [--by outcome] [--pcc]
        [--moderators col1,col2] [--pet-alpha 0.10] [--no-figure]
    python3 scripts/meta_analysis.py --csv estimates.csv --out results_dir/

Input: 06_estimates.csv - one row per estimate:
    est_id, ref_id (study; used for clustering), estimate, se, t, df,
    effect_type (raw | pcc), outcome, unit, horizon, sample, location, include, notes
Rows with include = N/no/0 are skipped. With --pcc (or effect_type = pcc), each
estimate is converted to a partial correlation r = t / sqrt(t^2 + df) with
se = sqrt((1 - r^2) / df); t defaults to estimate/se when blank.

Reported per group (--by splits by a column such as outcome or unit):
  * simple mean and median
  * fixed-effect (inverse-variance) average with its classic SE
  * random effects, DerSimonian-Laird: tau^2, I^2, Q and its p-value
  * FAT-PET meta-regression  estimate_i = b0 + b1*se_i  (WLS, weights 1/se^2):
    b1 tests funnel asymmetry (FAT), b0 is the precision-effect estimate (PET)
  * PEESE  estimate_i = b0 + b1*se_i^2  (WLS, weights 1/se^2)
  * PET-PEESE: PEESE's b0 when PET rejects b0 = 0 at --pet-alpha (two-sided),
    otherwise PET's b0. The alpha used is printed; report it.
  * WAAP: weighted average of the adequately powered estimates (se <= |FE|/2.8,
    i.e. power >= 80% at 5% two-sided if the FE average were the true effect),
    plus the median power of all estimates
  * optional moderators added to the FAT-PET regression
Meta-regression SEs are cluster-robust by ref_id (CR1); with fewer than 10
clusters they are unreliable, so the conventional WLS SE is printed as well.
Random-effects results assume independent estimates - several estimates per study
violate that, so treat them as descriptive and lean on the clustered regressions.

Outputs (in 08_meta/ or --out): meta_summary.md, meta_results.json, funnel_<group>.png
Requires numpy; matplotlib for the funnel plot.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import FILES, read_csv  # noqa: E402

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


# ---------------------------------------------------------------------------
# Distribution functions (no SciPy dependency)
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_pvalue(t: float, df: float) -> float:
    """Two-sided p-value of a t statistic; normal approximation when df is None/inf."""
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return float("nan")
    if df is None or df == math.inf or df > 1e6:
        return math.erfc(abs(t) / math.sqrt(2.0))
    if df <= 0:
        return float("nan")
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def gammaincc(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x)."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1.0:                       # series for P, return 1 - P
        ap, s, delta = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1.0
            delta *= x / ap
            s += delta
            if abs(delta) < abs(s) * 3e-16:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - gln)
    tiny = 1e-300                          # continued fraction for Q
    b = x + 1.0 - a
    c, d = 1.0 / tiny, 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = b + an / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------
def wls(y, X, w, clusters=None) -> dict:
    """Weighted least squares with conventional and cluster-robust (CR1) SEs."""
    y, X, w = np.asarray(y, float), np.asarray(X, float), np.asarray(w, float)
    n, k = X.shape
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], y * sw
    xtx_inv = np.linalg.pinv(Xw.T @ Xw)
    beta = xtx_inv @ (Xw.T @ yw)
    e = yw - Xw @ beta
    dof = max(n - k, 1)
    s2 = float(e @ e) / dof
    se_conv = np.sqrt(np.clip(np.diag(xtx_inv) * s2, 0, None))
    out = {"beta": beta, "se_conv": se_conv, "df_conv": dof, "n": n, "k": k, "s2": s2}
    if clusters is not None:
        groups = defaultdict(list)
        for i, g in enumerate(clusters):
            groups[g].append(i)
        G = len(groups)
        meat = np.zeros((k, k))
        for idx in groups.values():
            u = Xw[idx].T @ e[idx]
            meat += np.outer(u, u)
        corr = (G / (G - 1)) * ((n - 1) / dof) if G > 1 else float("nan")
        V = corr * xtx_inv @ meat @ xtx_inv
        out.update(se_cl=np.sqrt(np.clip(np.diag(V), 0, None)), df_cl=max(G - 1, 1), G=G)
    return out


def coef(res: dict, j: int, robust: bool = True) -> dict:
    use_cl = robust and "se_cl" in res and res.get("G", 0) > 1
    se = float(res["se_cl"][j] if use_cl else res["se_conv"][j])
    df = res["df_cl"] if use_cl else res["df_conv"]
    b = float(res["beta"][j])
    t = b / se if se > 0 else float("nan")
    return {"b": b, "se": se, "t": t, "p": t_pvalue(t, df), "df": df,
            "se_type": "cluster-robust (CR1)" if use_cl else "conventional WLS"}


def fixed_effect(y, se) -> dict:
    w = 1.0 / se ** 2
    b = float(np.sum(w * y) / np.sum(w))
    s = float(math.sqrt(1.0 / np.sum(w)))
    return {"b": b, "se": s, "ci": (b - 1.96 * s, b + 1.96 * s)}


def random_effects_dl(y, se) -> dict:
    w = 1.0 / se ** 2
    k = len(y)
    b_fe = np.sum(w * y) / np.sum(w)
    Q = float(np.sum(w * (y - b_fe) ** 2))
    dfq = k - 1
    C = float(np.sum(w) - np.sum(w ** 2) / np.sum(w))
    tau2 = max(0.0, (Q - dfq) / C) if C > 0 else 0.0
    wr = 1.0 / (se ** 2 + tau2)
    b = float(np.sum(wr * y) / np.sum(wr))
    s = float(math.sqrt(1.0 / np.sum(wr)))
    i2 = max(0.0, (Q - dfq) / Q) if Q > 0 else 0.0
    return {"b": b, "se": s, "ci": (b - 1.96 * s, b + 1.96 * s), "tau2": tau2, "I2": i2,
            "Q": Q, "Q_df": dfq, "Q_p": gammaincc(dfq / 2.0, Q / 2.0) if dfq > 0 else float("nan")}


def analyse_group(rows: list[dict], moderators: list[str], pet_alpha: float) -> dict:
    y = np.array([r["_y"] for r in rows])
    se = np.array([r["_se"] for r in rows])
    cl = [r.get("ref_id") or r.get("est_id") for r in rows]
    w = 1.0 / se ** 2
    n, G = len(y), len(set(cl))
    res = OrderedDict(n_estimates=n, n_studies=G, mean=float(np.mean(y)), median=float(np.median(y)))
    res["fixed_effect"] = fixed_effect(y, se)
    res["random_effects_dl"] = random_effects_dl(y, se) if n >= 2 else None

    notes = []
    if n < 10:
        notes.append(f"Only {n} estimates: publication-bias tests have little power; treat them as indicative.")
    if G < 10:
        notes.append(f"Only {G} studies: cluster-robust SEs are unreliable; conventional SEs shown alongside.")

    if n >= 3:
        pet = wls(y, np.column_stack([np.ones(n), se]), w, cl)
        peese = wls(y, np.column_stack([np.ones(n), se ** 2]), w, cl)
        res["pet"] = {"b0": coef(pet, 0), "b0_conventional": coef(pet, 0, robust=False)}
        res["fat"] = {"b1": coef(pet, 1), "b1_conventional": coef(pet, 1, robust=False)}
        res["peese"] = {"b0": coef(peese, 0), "b0_conventional": coef(peese, 0, robust=False)}
        use_peese = res["pet"]["b0"]["p"] < pet_alpha
        res["pet_peese"] = {"selected": "PEESE" if use_peese else "PET",
                            "estimate": res["peese"]["b0"] if use_peese else res["pet"]["b0"],
                            "rule": f"PEESE if PET rejects b0 = 0 at {pet_alpha:g} (two-sided), else PET"}
        if moderators:
            cols = [np.ones(n), se] + [np.array([r["_mod"][m] for r in rows]) for m in moderators]
            mra = wls(y, np.column_stack(cols), w, cl)
            names = ["const (PET)", "se (FAT)"] + moderators
            res["mra_moderators"] = {nm: coef(mra, j) for j, nm in enumerate(names)}
    else:
        notes.append("Fewer than 3 estimates: no meta-regression.")

    fe = abs(res["fixed_effect"]["b"])
    powered = se <= fe / 2.8 if fe > 0 else np.zeros(n, bool)
    power = [norm_cdf(fe / s - 1.96) + norm_cdf(-fe / s - 1.96) for s in se]
    res["waap"] = {"n_adequately_powered": int(powered.sum()),
                   "estimate": fixed_effect(y[powered], se[powered]) if powered.sum() >= 1 else None,
                   "median_power": float(np.median(power))}
    if powered.sum() == 0:
        notes.append("No adequately powered estimate: WAAP not available; the PET-PEESE result carries more weight.")
    res["notes"] = notes
    return res


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def to_float(v):
    try:
        v = str(v).strip()
        return float(v) if v else None
    except ValueError:
        return None


def prepare(rows: list[dict], pcc: bool, moderators: list[str]) -> tuple[list[dict], list[str]]:
    kept, problems = [], []
    for r in rows:
        if str(r.get("include", "")).strip().lower() in ("n", "no", "0", "false"):
            continue
        rid = r.get("est_id") or "?"
        est, se, t, df = (to_float(r.get(k)) for k in ("estimate", "se", "t", "df"))
        if pcc or (r.get("effect_type") or "").strip().lower() == "pcc":
            if t is None and est is not None and se:
                t = est / se
            if t is None or not df or df <= 0:
                problems.append(f"{rid}: PCC needs t (or estimate+se) and df > 0")
                continue
            y = t / math.sqrt(t * t + df)
            s = math.sqrt((1 - y * y) / df)
        else:
            if est is None or not se or se <= 0:
                problems.append(f"{rid}: needs estimate and se > 0")
                continue
            y, s = est, se
        mods = {}
        for m in moderators:
            v = to_float(r.get(m))
            if v is None:
                problems.append(f"{rid}: moderator '{m}' missing or non-numeric")
                break
            mods[m] = v
        else:
            kept.append(dict(r, _y=y, _se=s, _mod=mods))
    return kept, problems


def fmt(c: dict | None) -> str:
    if not c:
        return "-"
    stars = "" if c.get("p") is None or math.isnan(c["p"]) else f", p = {c['p']:.3f}"
    return f"{c['b']:.4f} (SE {c['se']:.4f}{stars})"


def summary_md(results: dict, meta: dict) -> str:
    L = ["# Meta-analysis summary", "",
         f"Effect metric: {meta['metric']} · Grouping: {meta['by'] or 'none'} · PET-PEESE alpha: {meta['pet_alpha']:g}",
         f"Estimates used: {meta['n_used']} · skipped: {meta['n_skipped']}", ""]
    for g, r in results.items():
        L += [f"## {g}", "",
              f"Estimates {r['n_estimates']} · studies {r['n_studies']} · mean {r['mean']:.4f} · median {r['median']:.4f}", "",
              "| Estimator | Estimate (SE, p) | Notes |", "|---|---|---|"]
        fe = r["fixed_effect"]
        L.append(f"| Fixed effect | {fe['b']:.4f} (SE {fe['se']:.4f}) | 95% CI {fe['ci'][0]:.4f} to {fe['ci'][1]:.4f} |")
        re = r.get("random_effects_dl")
        if re:
            L.append(f"| Random effects (DL) | {re['b']:.4f} (SE {re['se']:.4f}) | tau^2 {re['tau2']:.4g}, "
                     f"I^2 {re['I2']:.1%}, Q {re['Q']:.2f} (df {re['Q_df']}, p {re['Q_p']:.3f}) |")
        if "pet" in r:
            L.append(f"| FAT (b1 on se) | {fmt(r['fat']['b1'])} | conventional: {fmt(r['fat']['b1_conventional'])} |")
            L.append(f"| PET (b0) | {fmt(r['pet']['b0'])} | conventional: {fmt(r['pet']['b0_conventional'])} |")
            L.append(f"| PEESE (b0) | {fmt(r['peese']['b0'])} | conventional: {fmt(r['peese']['b0_conventional'])} |")
            L.append(f"| PET-PEESE -> {r['pet_peese']['selected']} | {fmt(r['pet_peese']['estimate'])} | {r['pet_peese']['rule']} |")
        wa = r["waap"]
        L.append(f"| WAAP | {fmt(wa['estimate']) if wa['estimate'] else 'n/a'} | {wa['n_adequately_powered']} adequately "
                 f"powered; median power {wa['median_power']:.0%} |")
        if r.get("mra_moderators"):
            L += ["", "Meta-regression with moderators (cluster-robust):", "",
                  "| Term | Coefficient (SE, p) |", "|---|---|"]
            for nm, c in r["mra_moderators"].items():
                L.append(f"| {nm} | {fmt(c)} |")
        if r["notes"]:
            L += [""] + [f"- {n}" for n in r["notes"]]
        L.append("")
    if meta["problems"]:
        L += ["## Skipped rows", ""] + [f"- {p}" for p in meta["problems"]] + [""]
    return "\n".join(L)


def funnel(rows: list[dict], res: dict, path: Path, title: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    y = [r["_y"] for r in rows]
    prec = [1.0 / r["_se"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(y, prec, s=18, alpha=0.6, color="#3b6ea5", edgecolor="none", label="estimates")
    ax.axvline(res["fixed_effect"]["b"], color="#888888", lw=1, ls="--", label="fixed effect")
    if "pet_peese" in res:
        ax.axvline(res["pet_peese"]["estimate"]["b"], color="#c0504d", lw=1.2,
                   label=f"{res['pet_peese']['selected']} estimate")
    ax.axvline(0, color="#222222", lw=0.6)
    ax.set_xlabel("estimate")
    ax.set_ylabel("precision (1 / SE)")
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return True


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if np is not None and isinstance(o, np.generic):
        return o.item()
    if isinstance(o, float) and math.isnan(o):
        return None
    return o


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", help="review folder containing 06_estimates.csv")
    ap.add_argument("--csv", help="explicit estimates CSV (instead of the folder)")
    ap.add_argument("--out", help="output directory (default: <folder>/08_meta)")
    ap.add_argument("--by", default="", help="column to split groups by, e.g. outcome")
    ap.add_argument("--pcc", action="store_true", help="convert all estimates to partial correlations")
    ap.add_argument("--moderators", default="", help="comma-separated numeric moderator columns")
    ap.add_argument("--pet-alpha", type=float, default=0.10)
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()

    if np is None:
        print("numpy is required: pip install numpy")
        return 2
    if args.csv:
        src = Path(args.csv)
        out = Path(args.out) if args.out else src.parent / FILES["meta_dir"]
    elif args.folder:
        src = Path(args.folder) / FILES["estimates"]
        out = Path(args.out) if args.out else Path(args.folder) / FILES["meta_dir"]
    else:
        ap.error("give a review folder or --csv")
    if not src.exists():
        print(f"{src} not found")
        return 1
    out.mkdir(parents=True, exist_ok=True)

    moderators = [m.strip() for m in args.moderators.split(",") if m.strip()]
    raw = read_csv(src)
    rows, problems = prepare(raw, args.pcc, moderators)
    if not rows:
        print("No usable estimates.")
        for p in problems:
            print("  " + p)
        return 1

    groups = defaultdict(list)
    for r in rows:
        groups[(r.get(args.by) or "(blank)") if args.by else "all estimates"].append(r)

    results, warnings = OrderedDict(), []
    for g, grp in groups.items():
        units = {(r.get("unit") or "").strip() for r in grp if (r.get("unit") or "").strip()}
        if len(units) > 1 and not args.pcc:
            warnings.append(f"group '{g}' mixes units {sorted(units)} - split with --by unit or use --pcc")
        results[g] = analyse_group(grp, moderators, args.pet_alpha)
        if not args.no_figure:
            safe = "".join(ch if ch.isalnum() else "_" for ch in str(g))[:40]
            funnel(grp, results[g], out / f"funnel_{safe}.png", f"Funnel plot - {g}")

    meta = {"metric": "partial correlation" if args.pcc else "as reported", "by": args.by,
            "pet_alpha": args.pet_alpha, "n_used": len(rows), "n_skipped": len(raw) - len(rows),
            "problems": problems + warnings}
    text = summary_md(results, meta)
    (out / "meta_summary.md").write_text(text, encoding="utf-8")
    (out / "meta_results.json").write_text(json.dumps(jsonable({"meta": meta, "results": results}),
                                                      indent=2, ensure_ascii=False), encoding="utf-8")
    print(text)
    for w in warnings:
        print("WARNING: " + w)
    print(f"Wrote {out / 'meta_summary.md'} and meta_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
