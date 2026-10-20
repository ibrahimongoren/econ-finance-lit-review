# Synthesis, answers and certainty

Read at Stage 8. Covers how to answer each research question, how to grade the
certainty of that answer, when and how to pool estimates, and how to write the
synthesis.

## Contents
1. Answer format
2. Certainty grading (GRADE-style, adapted to economics)
3. Quantitative synthesis protocol
4. Evidence map and methods-comparison table
5. Writing rules and calibrated language
6. Weakness patterns and what the literature leaves out

---

## 1. Answer format

Every research question in the protocol gets an answer block at the top of the
report. Keep it short; the body of the report carries the detail.

```
RQ1 — Does a monetary tightening reduce bank lending more in high-uncertainty periods?

Answer: Yes, in most well-identified studies. The additional contraction is
roughly X–Y pp of loan growth after 12 months per 100 bp, concentrated in
smaller and less-capitalised banks.
Certainty: Moderate — consistent sign across identification strategies, but
estimates differ widely in size (I² 78%) and most evidence is from advanced
economies (indirect for emerging markets).
Evidence base: 14 studies (52 estimates); bank-level panels with high-frequency
or narrative shocks; US, euro area, 3 EMEs; 2005–2024 samples. [citations]
Where the answer changes: effects are weaker or insignificant in studies that
use survey-based uncertainty measures [citations].
```

Rules
- Direction first, then magnitude with units, horizon and the shock size it refers to.
- Give a range across credible studies, not a single "average" unless a meta-analysis
  produced it (then name the estimator: e.g. "PET-PEESE-corrected").
- If the evidence cannot answer the question, say so and say why (no studies, only
  correlational studies, contradictory findings with no diagnosable cause).
- Every number in an answer block has a location in `06_extraction.csv` or
  `08_meta/meta_summary.md`.

## 2. Certainty grading (GRADE-style, adapted to economics)

GRADE (Guyatt et al., 2008) rates how much confidence an estimate deserves. The
domains below translate it to economics evidence; this adaptation is the skill's
own, so describe it as "GRADE-style" in reports.

**Starting level**
- *High* when the body of evidence rests mainly on credible identification for the
  question: natural or field experiments, well-defended IV, DiD with
  heterogeneity-robust estimators, RD, synthetic control, SVAR/LP identified with
  external instruments, high-frequency or narrative shocks.
- *Low* when it rests mainly on correlations, reduced-form regressions without an
  identification argument, or calibrated models without empirical validation.

**Downgrade one level for each serious concern**
| Domain | Downgrade when |
|---|---|
| Risk of bias | most weight sits on studies scoring ≤ 6/12 in `07_appraisal.csv` |
| Inconsistency | signs or sizes conflict and the conflict is not explained by method, sample or period |
| Indirectness | the evidence comes from other contexts, outcomes or horizons than the question asks about (e.g. advanced-economy evidence for an emerging-market question) |
| Imprecision | few studies, or intervals that include both economically meaningful and null effects |
| Publication bias | FAT significant, PET-PEESE or WAAP well below the simple average, bunching just above significance thresholds, or only published studies found |

**Upgrade one level (rarely) when**
- effects are large and consistent across different identification strategies;
- several independent designs converge on the same answer;
- effects rise monotonically with shock size (dose-response).

**Meaning to give readers**
| Grade | Plain meaning |
|---|---|
| High | Further research is unlikely to change the answer. |
| Moderate | Further research may change the size, probably not the direction. |
| Low | Further research is likely to change the answer. |
| Very low | The answer is very uncertain. |

Report the domains that moved the grade in one line; that line is what referees read.

## 3. Quantitative synthesis protocol

**When to pool.** Only estimates of the same quantity: same outcome definition,
unit, horizon and shock normalization (or after converting to partial correlations).
Pool when at least ten comparable estimates exist; with fewer, describe instead.
Never pool an elasticity with a semi-elasticity, levels with growth rates, or
impulse responses at different horizons.

**Building `06_estimates.csv`** (one row per estimate):
- `ref_id` is the study (both reports of one study share it) — used for clustering.
- `estimate` and `se`; if only a 95% CI is reported, `se = (upper − lower) / 3.92`
  for a symmetric interval; if only t, enter `t` and `df`. Record any derivation in
  `notes` and the table/page in `location`.
- Harmonize signs (e.g. effects of a tightening, not an easing) before entry.
- `effect_type` `pcc` converts to partial correlations: r = t / sqrt(t² + df),
  se = sqrt((1 − r²) / df).
- Mark non-preferred estimates `include = N` to run a one-estimate-per-study check.

**Running**
```bash
python3 scripts/meta_analysis.py litrev-<slug>/ --by outcome
python3 scripts/meta_analysis.py litrev-<slug>/ --pcc --moderators method_iv,emerging
```

**Reading the output**
- *Fixed effect* and *random effects* (DerSimonian & Laird, 1986) averages, with τ²,
  Q and I² (Higgins & Thompson, 2002) for heterogeneity. Random effects assume
  independent estimates; with several estimates per study treat them as descriptive.
- *FAT–PET–PEESE* (Stanley & Doucouliagos, 2014): the coefficient on the standard
  error tests funnel asymmetry; the intercept is the effect corrected for selection.
  The script switches to PEESE when PET rejects a zero effect at the stated alpha.
- *WAAP*: the weighted average of adequately powered estimates, and median power —
  the logic Ioannidis et al. (2017) apply to economics literatures.
- *Moderators* explain heterogeneity (method, region, period, data frequency); put
  them in the PET regression and interpret coefficients as differences in reported
  effects, not causal effects.
- Selection-model corrections (Andrews & Kasy, 2019) need dedicated software; if you
  do not run one, say so.

**Reporting** follows the MAER-NET guidelines (Havránek et al., 2020) and the
practitioner's guide of Iršová et al. (2024): search and inclusion, the estimates
dataset, estimators, bias tests and corrections, heterogeneity analysis,
robustness, and data availability (ship `06_estimates.csv`).

## 4. Evidence map and methods-comparison table

**Evidence map** — counts of included studies by theme × method family × region
(or period). Empty cells are candidate gaps for Stage 9; note them.

| Theme \ method | SVAR/LP | Bank-level panel | DSGE | DiD/event study | Other |
|---|---|---|---|---|---|
| Lending channel | | | | | |
| Risk-taking channel | | | | | |

**Methods-comparison table** — one row per included study (or per study group):

| Study | Context and sample | Method | Identification | Outcome | Finding (sign, size, units) | Credibility |
|---|---|---|---|---|---|---|

## 5. Writing rules and calibrated language

- Organize by argument. Each section advances a claim about the state of knowledge;
  studies are evidence for it.
- Report direction and magnitude with units; explain heterogeneity before averaging
  it; weight by credibility and say so.
- Diagnose disagreement rather than averaging it away: which method, sample, period
  or measure separates the camps?
- Separate what a study shows from what its authors conjecture.

| Evidence state | English | Türkçe |
|---|---|---|
| several well-identified studies converge | "The evidence consistently indicates…" | "Kanıtlar tutarlı biçimde … göstermektedir" |
| most agree, identification mixed | "The balance of evidence suggests…" | "Kanıtların ağırlığı … yönündedir" |
| diagnosable disagreement | "Findings diverge: [A]…, [B]…, plausibly because…" | "Bulgular ayrışmaktadır: [A] …, [B] …; olası neden …" |
| undiagnosed disagreement | "The evidence is contested; the source of disagreement is unresolved" | "Kanıtlar tartışmalıdır; ayrışmanın kaynağı belirsizdir" |
| single study | "A single study reports…; it has not been replicated" | "Tek bir çalışma … bildirmektedir; tekrarlanmamıştır" |
| nothing found | "No study meeting the criteria was found in this search" | "Bu taramada ölçütleri karşılayan çalışma bulunamadı" |

For other output languages, translate these phrasings and keep the same
calibration.

## 6. Weakness patterns and what the literature leaves out

The study cards (`study-cards.md`) feed the synthesis in two ways.

**Weakness patterns.** From `study_cards.py stats`, report the 3–5 weaknesses that recur, with
counts and the studies concerned, and say what each does to the answer:
- a high-severity weakness shared by most studies lowers certainty (risk of bias / imprecision in
  §2) — e.g. "9 of 14 studies treat survey expectations as exogenous; their forward-looking
  weights are likely biased upward";
- a weakness confined to one method family explains disagreement — compare the studies that
  avoid it with those that do not;
- name the studies that handle the weakness well; they anchor the answer.

**What the literature leaves out.** Group the cards' "what it left out" entries: countries,
periods, variables or channels, frequencies and methods that no included study covers. Cross the
groups with the evidence map; a cell that is empty and also listed in several cards is a strong
gap candidate for Stage 9 (it still needs the dated searches that found nothing and a feasible
design).

Write both as argument, not lists: "The evidence on X rests mostly on Y, which shares weakness
Z; the few studies that avoid Z find …".

