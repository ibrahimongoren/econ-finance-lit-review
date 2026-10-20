# Extraction fields, method taxonomy and credibility rubric

Read at Stage 6 (extraction) and Stage 7 (appraisal). Method names are given
without citations on purpose: when a review discusses a method's literature, those
papers go through Stage 5 verification like any other source.

## Contents
1. Extraction fields (`06_extraction.csv`) and the estimates file (`06_estimates.csv`)
2. Method taxonomy for coding `method_family` and `identification`
3. Credibility rubric (`07_appraisal.csv`)
4. Comparing findings across studies
5. Context notes for emerging and developing economies

---

## 1. Extraction fields

| Field | What to record | Example |
|---|---|---|
| `theme` | the synthesis theme the study belongs to (same label as its card) | "Expectations and persistence" |
| `country_region` | countries or panel, comma-separated (the regions figure counts each) | "Türkiye"; "Brazil, Mexico"; "28 EMEs" |
| `sample_period` | first–last observation | "2006M1–2023M12" |
| `frequency` | M, Q, A, daily, intraday | "M" |
| `unit` | economy, bank, firm, household, asset | "bank-level, 45 banks" |
| `data_source` | named databases | "TCMB EVDS; BDDK" |
| `method_family` | from §2 | "SVAR" |
| `identification` | the assumption that buys causality | "sign restrictions on impact" |
| `outcome` | dependent variable and transformation | "CPI inflation, y/y %" |
| `key_regressors` | treatment, shock, interaction | "policy-rate shock × high-uncertainty regime" |
| `direction` | +, −, 0 (insignificant), mixed | "−" |
| `magnitude_units` | number **with units and horizon** | "−0.3 pp after 12 months per 100 bp" |
| `uncertainty` | SE, CI or band type | "68% credible band excludes 0 at h=6–15" |
| `location` | where the number is | "Table 3, col. 2; Fig. 4" |
| `heterogeneity` | how the effect varies | "larger in high-dollarisation periods" |
| `robustness` | checks reported | "alternative shock series, sub-samples" |
| `limitations` | authors' and yours | "short post-break sample" |
| `evidence_level` | `[FT]` full text / `[AB]` abstract only | "[FT]" |

If the number is not in the paper, leave `magnitude_units` empty — do not compute
or infer it — and note why.

**`06_estimates.csv`** — one row per comparable estimate, for meta-analysis:
`est_id, ref_id, estimate, se, t, df, effect_type (raw|pcc), outcome, unit, horizon,
sample, location, include, notes`. Add numeric moderator columns as needed (e.g.
`method_iv` = 1/0, `emerging` = 1/0) and pass them with `--moderators`. Rules for
deriving SEs from intervals, harmonizing signs and converting to partial
correlations are in `synthesis.md` §3.

## 2. Method taxonomy

Use these labels in `method_family`; put the specific identifying assumption in
`identification`.

**Macro and monetary time series**
- VAR / SVAR — identification: recursive (Cholesky), long-run, sign restrictions,
  external instruments (proxy SVAR), high-frequency surprises, narrative shocks,
  heteroskedasticity.
- Local projections (LP), incl. state-dependent and panel LP.
- Bayesian VAR, FAVAR, global VAR, panel VAR.
- Time-varying parameter VAR (TVP-VAR), stochastic volatility.
- Regime-switching: Markov-switching (MS-VAR), threshold / smooth-transition models.
- DSGE: calibrated, Bayesian-estimated; note the frictions and the policy rule.
- Unit-root and cointegration with breaks (e.g. LM tests with breaks), ARDL bounds,
  Johansen; note how breaks are dated.
- Volatility: GARCH family, realized measures; quantile regression, growth-at-risk.

**Micro-econometric causal designs**
- Difference-in-differences — note whether treatment timing is staggered and
  whether heterogeneity-robust estimators are used.
- Event study, IV / 2SLS (report first-stage strength), regression discontinuity,
  synthetic control, matching, panel fixed effects, dynamic panel GMM (report
  instrument count and tests).

**Finance**
- Event studies (abnormal returns, window), Fama–MacBeth and time-series factor
  tests, portfolio sorts, panel regressions with clustered standard errors,
  high-frequency identification around announcements, bank-level lending
  regressions with loan-demand controls.

**Climate economics and climate finance**
- Integrated assessment models, climate-risk indicators (physical vs. transition),
  text-based climate indices, carbon-price pass-through, stress-test scenarios.

**Machine learning**
- LASSO / elastic net, tree ensembles, neural nets — record whether used for
  prediction or for causal estimation (e.g. double/debiased ML), and the
  validation scheme.

**Descriptive / other**
- Descriptive statistics, case studies, surveys, theory-only papers: code them,
  but they rarely answer causal questions — say so in synthesis.

## 3. Credibility rubric (0–2 each, total 0–12)

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Identification | correlation presented as causal; no argument | plausible but contestable assumption, partly defended | clearly stated assumption, defended with tests or institutional detail |
| Data and measurement | key variables proxied loosely or undocumented | reasonable proxies, some measurement concerns | well-measured, documented, appropriate frequency |
| Inference | SEs ignore obvious dependence, weak instruments untested, many tests unadjusted | mostly appropriate, some gaps | appropriate clustering/HAC, weak-IV robust where relevant, bands reported |
| Robustness | none | some alternative specifications | systematic: alternative identification, samples, definitions |
| Transparency | no data/code, unclear sample construction | partial (data public, no code) | replication package or full code and data; pre-registration where relevant |
| Relevance to the review question | tangential | partly matches PECO | matches population, exposure and outcome |

Use the total to weight synthesis ("we place more weight on…") and say so. Do not
use it to exclude studies silently; exclusions belong in the protocol criteria.

## 4. Comparing findings across studies

- Harmonize units before comparing (pp vs. %, per 100 bp vs. per 1 s.d. shock,
  horizon). If they cannot be harmonized, compare signs and significance only and
  say so.
- Explain heterogeneity before averaging it: method, identification, sample,
  period, frequency, country group.
- Vote counting (how many significant) is not evidence of an effect size; use it
  only to describe the literature.
- Meta-analysis needs comparable estimates *with* standard errors; see
  `synthesis.md` §3 and the reporting guidelines listed in SKILL.md §11.

## 5. Context notes for emerging and developing economies

- Long samples often cross distinct policy regimes, crises and redenominations;
  check whether a study models breaks or regimes, and where it dates them, before
  comparing it with others.
- Exchange-rate pass-through, dollarisation, capital flows and fiscal dominance can
  dominate transmission; code them as mechanisms when studies test them.
- Official data revisions, base-year changes and informality matter; record the data
  vintage and coverage when a study reports them.
- National-language studies (e.g. DergiPark for Türkiye, SciELO for Latin America,
  J-STAGE or KCI for Japan and Korea) can carry most of the country-specific
  evidence; screen them with the same criteria and rubric.
- Evidence from advanced economies is *indirect* for an emerging-market question;
  say so in the certainty grade (`synthesis.md` §2).
