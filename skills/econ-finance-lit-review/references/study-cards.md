# Study cards — three-pass reading, what each study did and left out, its weaknesses

Read at Stage 6. Every included study published inside the literature window gets one card;
the user sees every card in the chat (with the study's verified link) and, if they asked for it,
in the report. Older canonical works are verified and cited as background, but not carded.

## Contents
1. The corpus that gets cards
2. Getting the full text
3. The three passes
4. "What did it do?" and "What did it leave out?"
5. Weakness analysis: taxonomy, severity, basis, grounding
6. Files and fields
7. Chat format (TR / EN)
8. Quality bar and checks
9. From cards to synthesis and gaps

---

## 1. The corpus that gets cards

- **Window.** The user's years (e.g. 2020–2026, "2020–günümüz") or, when none were given, the last
  five years [Y−5, Y] (2021–2026 in 2026). `00_protocol.md` holds it as `Literature window: Y0-Y1`;
  every script reads it from there.
- **All studies, not a sample.** Every record that passes screening and verification and whose
  publication year (issue year of the version of record) lies in the window gets a card. A working
  paper and its journal version are one study: card the journal version, mention the WP.
- `study_cards.py init` creates a `todo` card for each such study and lists the out-of-window
  studies as background. If the included set is large (> 60 studies), say so at C2 and offer the
  user an order (e.g. by theme, most relevant first) — but every card is still written.

## 2. Getting the full text

Passes 2 and 3 need the full text. In this order:

1. `find_fulltext.py` — legal open-access copies via Unpaywall, OpenAlex and Semantic Scholar
   (`--dry-run` prints the URLs for the web fetch tool when the shell has no network).
2. The working-paper version (NBER, CEPR, IMF, BIS, ECB, Fed, central banks, SSRN, RePEc, arXiv),
   the authors' pages, institutional repositories, DergiPark/SciELO article pages.
3. Connectors that hold full text (a Zotero library through zotero-mcp, Elicit on paid plans,
   arXiv through arxiv-mcp-server).
4. The user: list the paywalled studies and ask for PDFs through their library.

Never use shadow libraries (Sci-Hub, LibGen, mirrors) or tools that call them — including the
`download_scihub` and `download_with_fallback` tools of paper-search-mcp. If no full text is
available, write an abstract-level card (`evidence_level` = AB): pass 1 only, the other passes
marked as not possible, and claims phrased "according to its abstract".

## 3. The three passes

Each pass answers fixed questions in 2–4 sentences, in the user's language, with locations
(section, table, page). Read in this order; later passes correct earlier impressions.

**Pass 1 — Abstract → Conclusion** (`pass1_abstract_conclusion`)
- What question, which sample (countries, period, frequency), which method?
- The main result: sign, magnitude with units and horizon, significance as reported.
- What the conclusion claims beyond the abstract (policy advice, generality) — and whether the
  claims match the evidence the abstract describes. Note any mismatch; it often becomes a weakness.

**Pass 2 — Introduction → Methodology** (`pass2_intro_method`)
- Motivation and the contribution the authors claim (new data, method, context, mechanism).
- Specification: dependent variable, key regressors, controls; for a Phillips curve, e.g., the
  expectations measure (survey, model-based, market), the slack measure, the lags.
- Identification and estimation: instruments, regime or threshold definition, structural
  assumptions, sample splits, estimator (GMM, MS-VAR, TVP-VAR, LP, ML), inference (SEs, bootstrap).
- Data sources and transformations (filters, interpolation, deflators, breaks).
- Robustness the authors report (Table/Appendix).

**Pass 3 — Literature review** (`pass3_literature`)
- Which strands the paper positions itself in, and the 2–4 works it builds on most directly.
- The gap it says it fills; whether that gap was really open when written.
- Relevant strands or recent work it does not engage with (dated to the paper's own time).

## 4. "What did it do?" and "What did it leave out?"

**NE YAPMIŞ? / WHAT DID IT DO?** (`what_it_did`) — one compact paragraph: question → data
(where, when, frequency) → method → main finding (direction, magnitude, units) → claimed
contribution. A reader who sees only this paragraph should know what the study established.

**NEYİ EKSİK BIRAKMIŞ? / WHAT DID IT LEAVE OUT?** (`what_it_left_out`) — scope the study did not
cover, judged against (a) the literature and (b) the user's research question:
- variables or channels not modeled (e.g. no climate-risk or geopolitical-risk index; no
  exchange-rate pass-through), countries or periods not covered, frequencies not used;
- methods not tried (nonlinearity, time variation, regime dependence, out-of-sample tests,
  ML benchmarks);
- the future work the authors themselves list (say so: "the authors note…").
Keep scope (left out) apart from flaws (weaknesses): not studying Türkiye is scope; an
instrument that fails the weak-instrument test is a weakness.

Then `relevance` — one sentence on how the study serves the user's own study (benchmark
specification, data source, contrasting result, method to adopt, gap to fill).

## 5. Weakness analysis

Every study gets at least one weakness, written as a specific, checkable statement about what
the study did. Generic phrases ("limited data", "further research is needed") do not count.

### Taxonomy (`category`)

| Category (TR) | What to check — economics and finance |
|---|---|
| `question_contribution` (Soru ve katkı) | contribution overstated; question already answered; result framed more broadly than the design supports |
| `theory_specification` (Teori ve model kurgusu) | ad hoc specification; omitted variables the theory requires; hybrid NKPC without both forward and backward terms; regimes not tied to theory |
| `identification` (Tanımlama) | endogeneity of expectations or slack untreated; weak or invalid instruments; reverse causality; regime/threshold variable endogenous; no exogenous variation for a causal claim |
| `data_measurement` (Veri ve ölçüm) | proxies (e.g. survey vs model-based expectations), interpolated or mixed frequencies, short samples, structural breaks ignored, revised vs real-time data, index construction (GPR, climate-risk indices) |
| `estimation_inference` (Tahmin ve çıkarım) | wrong standard errors (serial correlation, clustering, small samples), unreported diagnostics (weak IV, Hansen J, regime classification), over-fitting, look-ahead bias in ML |
| `robustness` (Sağlamlık) | single specification; lag or regime number fixed without tests; no alternative measures, subsamples or estimators |
| `external_validity` (Dış geçerlilik) | single country or period generalized; advanced-economy results applied to emerging markets; pre-2020 samples applied to the post-pandemic inflation regime |
| `literature_positioning` (Literatürdeki konumlanma) | misses key contemporary work; misstates prior findings; claimed gap not a gap |
| `transparency_replication` (Şeffaflık ve tekrarlanabilirlik) | no data or code; data sources or transformations unclear; results not reproducible from what is reported |
| `policy_interpretation` (Politika yorumu) | policy conclusions beyond the evidence; correlation read as a policy lever; ignores uncertainty bands |

### Severity (`severity`)

- **high** — threatens the main conclusion, or the use the user would make of the study
  (e.g. an endogenous expectations term in a hybrid NKPC estimated by OLS).
- **medium** — limits interpretation, magnitude or generality, but the direction likely survives.
- **low** — presentation, transparency or minor robustness gaps.

### Basis (`basis`) and grounding (`evidence_location`)

- `author-stated` — the authors acknowledge it (limitations section, footnote). Quote or
  paraphrase and give the location.
- `reviewer-identified` — your judgment. Ground it in what the paper shows (Table 3 reports no
  first-stage F; Section 2 uses linear interpolation from annual data) and give the location.
- For abstract-only cards, ground weaknesses in the abstract (`evidence_location` = `abstract`)
  and only where the abstract itself shows the problem (single country, annual data, 2000–2015
  sample). If nothing can be assessed, record no weakness and write in `notes`:
  "weaknesses not assessable from the abstract" (TR: "zayıf yönler özetten değerlendirilemedi").
- Fair judgment: assess against the paper's own question and the standards and data of its
  time; credit what it does well in `what_it_did`. Never attribute a flaw you did not see.

## 6. Files and fields

`06_study_cards.csv`: `ref_id, theme, pass1_abstract_conclusion, pass2_intro_method,
pass3_literature, what_it_did, what_it_left_out, relevance, full_text_source, evidence_level
(FT/AB), card_status (todo/draft/checked), notes`.

`06_weaknesses.csv` (one row per weakness): `ref_id, category, severity, weakness,
evidence_location, basis, notes`.

`theme` groups cards in the chat and the report; use the 3–7 themes of the synthesis. Keep the
coded fields for synthesis (`06_extraction.csv`: method family, country, magnitudes) consistent
with the card. Write cards in batches of 5–10 and save after each batch.

## 7. Chat format

`study_cards.py chat <folder> --lang tr --batch 8 --part N` prints a batch exactly like this
(EN labels with `--lang en`):

```
### Çalışma kartları — Bölüm 1 / 4 (1–8 / 29)

#### Tema: Beklentiler ve kalıcılık

**[1] Yılmaz ve Kaya (2024)** — *Başlık*

Dergi · https://doi.org/10.xxxx/xxxxx · ✅ doğrulandı · [FT]

- **1. tur — Özet → Sonuç:** …
- **2. tur — Giriş → Yöntem:** …
- **3. tur — Literatür taraması:** …
- **NE YAPMIŞ?** …
- **NEYİ EKSİK BIRAKMIŞ?** …
- **Zayıf yönler:**
  - [Tanımlama (nedensellik) · yüksek] … (inceleyen tespiti; Bölüm 3.2)
- **Çalışmana katkısı:** …
```

Send batches one after another in the same reply when they fit, otherwise across consecutive
messages ("Bölüm 2 / 4 …"), until every card has been shown; say at the start how many cards and
batches follow. Never shorten later batches to finish faster. The numbering matches the report.

## 8. Quality bar and checks

- `study_cards.py check <folder>` must pass: every in-window included study has a card; every
  card has pass 1, what it did, what it left out and relevance; [FT] cards have passes 2–3 and a
  full-text source; every weakness has a valid category, severity, basis and location.
- Spot audit: re-open the source for 10% of cards (at least 3) and every high-severity weakness;
  confirm the location; log it in `10_qa_log.md`.
- Every number in a card has its location; abstract-only cards say so.
- A card describes one study; claims across studies belong to the synthesis.

## 9. From cards to synthesis and gaps

- `study_cards.py stats` counts weaknesses by category and severity: report the patterns
  ("7 of 12 Markov-switching studies fix two regimes without testing") in the synthesis and in
  the weaknesses figure (`make_figures.py`).
- Recurring items of "what it left out" plus high-severity weaknesses that no study fixes are
  candidate research gaps for Stage 9 — each still needs its evidence and a feasible design.
