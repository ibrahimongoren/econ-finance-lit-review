---
name: econ-finance-lit-review
description: Comprehensive, systematic, link-verified literature reviews for any economics or finance topic or research question (macro, monetary, climate, finance, econometrics). It asks for the research question first and the details second, fixes the publication window (the user's years, else the last five years), searches Web of Science, Scopus, ScienceDirect, Google Scholar, Semantic Scholar, OpenAlex, Crossref and arXiv through APIs, connectors such as Consensus, Elicit and SciSpace, MCP servers or exports, then screens and verifies every study in that window. Each study gets a three-pass reading card (abstract to conclusion, introduction to method, literature review) saying what it did, what it left out and where it is weak; cards arrive in the chat with links, and an illustrated DOCX or PDF report is built on request. Use it whenever someone wants a literature review, systematic review, thesis literature chapter, research gaps or meta-analysis in economics or finance, even a bare topic (literatür taraması).
license: MIT
compatibility: Needs web search and web fetch. Python 3 runs the scripts (standard library for search and import, numpy for meta-analysis, matplotlib for figures, openpyxl for the workbook, python-docx plus optional pandoc and LibreOffice for the report). The API scripts need shell network access; otherwise connectors, web fetch and database exports are used. Uses research connectors and MCP servers (Consensus, Elicit, SciSpace, paper-search-mcp, arxiv-mcp-server, Zotero) and subagents when present.
metadata:
  version: "2.0.0"
  author: "İbrahim Öngören"
---

# Economics & Finance Literature Review — comprehensive, systematic, link-verified

Researchers bring a question; they need the answer the literature supports, how sure that
answer is, and a review a referee can check. For any economics or finance question this skill
delivers:

1. **An answer per research question** — direction, magnitude range with units, certainty grade.
2. **Every study in the publication window, one card each, in the chat** — with its verified
   link, three reading passes, *what it did*, *what it left out* and its **weaknesses**.
3. **Weakness patterns and research gaps** — what recurs across studies and what nobody covers.
4. **An audit trail** — search log, PRISMA 2020 flow, verification log, evidence workbook.
5. **On request, an illustrated report** (DOCX and/or PDF) with figures and schemas.

Default: when someone names an economics or finance topic or question, start the intake (§2),
then run the **comprehensive** pipeline. Use **rapid** mode only when asked for something
quick, **update** mode for an earlier review folder (§12.4).

---

## 1. Non-negotiables

A fabricated reference looks exactly like a real one — real authors, real journal, plausible
year, well-formed DOI. Only resolving it against a registry catches it.

1. **Nothing from memory reaches the output.** Papers you recall are search leads; they
   become references only after Stage 5 verifies them.
2. **No assembled identifiers.** Never build or "repair" a DOI, URL, volume, issue or page
   range; copy them from a fetched record. A guessed DOI usually resolves to another paper.
3. **A link counts only if it was checked in this session** (§8.2).
4. **Claims match what was read.** Tag claims `[FT]` (full text, with location) or `[AB]`
   (abstract only). Numbers need `[FT]` and a location; abstract-only claims say so.
5. **Weaknesses are grounded.** Every weakness names where it shows (section, table, page or
   "abstract") and whether the authors state it or you identified it. Never invent a flaw.
6. **Unverified items are shown, never hidden or silently fixed** — in a separate list, never
   used as evidence.
7. **Legal access only.** Respect database terms and rate limits; no shadow libraries
   (Sci-Hub, LibGen), no Sci-Hub tools of MCP servers, no CAPTCHA or bot-detection workarounds,
   no Google Scholar scraping; never print API keys.
8. **Comprehensive means documented, not guaranteed.** State sources, languages, window,
   retrieval caps, paywalled full texts and databases you could not reach.

If a user asks for a quick list "without checking", give it under the heading
`UNVERIFIED — model memory, may contain errors` and offer to verify it.

---

## 2. Intake — the question first, then the details

1. **Step 1: the research question.** If the user has not stated a clear, answerable question,
   ask for it — and only for it (`references/templates.md` §0). If they give a bare topic, offer
   2–4 concrete research questions to choose from.
2. **Step 2: the details**, in one message once the question is clear: publication years
   (default: the last five years), variables, data and frequency, countries, methods of
   interest, known key papers, the databases and tools they can access (WoS, Scopus,
   ScienceDirect, Zotero, Consensus, Elicit, API keys; exports they can upload), and the output
   (chat summaries always; report none / DOCX / PDF / both; language).
3. Skip any step the user already answered — restate what you understood instead. Never ask
   twice. If no answer comes (or the session is unattended), derive the question from the topic,
   take the defaults, record both under *Assumptions* and continue.

**Publication window.** The user's years ("2020–2026", "2020–günümüz", "since 2019") or, when
none are given, **the last five years [Y−5, Y]** — 2021–2026 in 2026. It goes into the protocol
as `Literature window: Y0-Y1` and every script reads it from there. Within the window the review
covers **all** studies that meet the criteria; earlier canonical works are verified and cited as
background, not carded.

---

## 3. Operating defaults

**Modes.** `comprehensive` (default): every stage, stopping rule enforced, full texts sought
for every included study. `rapid` (only on request): the same stages in light form — two
indexes, working-paper series, seeds and one snowball round; no consistency re-screen;
abstract-level cards allowed and tagged `[AB]`; every printed reference still verified; report
titled "Rapid review". `update`: §12.4.

**Language.** Write in the user's language; keep status codes and file names in English. Search
in English and in the languages of the countries in scope (Turkish for Türkiye, Spanish or
Portuguese for Latin America, …), translating every concept block.

**Checkpoints, not stops.** After the intake, the pipeline runs through. At C1 (after Stage 0),
C2 (after Stage 4) and C3 (after Stage 8) send one short progress message (templates §2). Stop
and wait only when (a) the question is still unclear, (b) the user asked for an interactive
review, or (c) a failure threshold in §8.5 is hit.

**Scale and parallel work.** If the session can start subagents, split Stage 3 by route or
source cluster, Stage 5 into batches of ~10 references and Stage 6 into batches of 5–8 cards.
Give each worker the non-negotiables, the relevant reference file and its own output file
(`03_records_part-A.csv`, ids prefixed `A-`). Without subagents, work the batches in sequence.

**Context hygiene.** The files hold the state. Do not paste whole CSVs into the conversation;
run the scripts and read their summaries.

**Scripts.** Run `scripts/<name>.py` by full path — `${CLAUDE_SKILL_DIR}/scripts/<name>.py`
where that placeholder is filled in (for example, Claude Code), otherwise the `scripts/` folder next
to this file. They need Python 3; without it, do the same steps by hand with the schemas in
`references/templates.md`. Keys come from environment variables or a `.env` file.

---

## 4. Working folder, stages and resume

```bash
python3 scripts/init_review.py "Short title" --lang tr --window 2021-2026   # --window omitted = last 5 years
```

creates `litrev-<slug>/`. The file prefix is the stage number:

| # | Stage | Output | Scripts | Done when |
|---|---|---|---|---|
| 0 | Question & protocol | `00_protocol.md` | `init_review.py` | RQs, window, PECO, criteria, routes, stopping rule written |
| 1 | Evidence scan & seeds | `01_evidence_scan.md`, `01_seeds.csv` | — | prior reviews logged; 5–15 verified seeds inside the window |
| 2 | Search strategy | `02_search_log.csv` (planned rows) | `search_sources.py --print-queries` | every route × concept block has a query, per language |
| 3 | Search & identification | `03_records*.csv`, `03_coverage.md` | `search_sources.py`, `import_records.py`, `dedupe_records.py`, `coverage_check.py` | stopping rule met |
| 4 | Screening | `04_screening.csv`, `04_prisma_flow.png` | `screening_check.py`, `prisma_flow.py` | every record decided; window applied; consistency check passed |
| 5 | Verification | `05_verification.csv` | `verify_refs.py` (open network) | every included and cited source has a status |
| 6 | Full texts & study cards | `06_fulltext.csv`, `06_study_cards.csv`, `06_weaknesses.csv`, `06_extraction.csv`, `06_estimates.csv` | `find_fulltext.py`, `study_cards.py` | `study_cards.py check` passes |
| 7 | Appraisal | `07_appraisal.csv` | — | every included study scored |
| 8 | Synthesis & answers | `08_synthesis.md`, `08_meta/` | `meta_analysis.py` | each RQ answered with a certainty grade |
| 9 | Research gaps | `09_gaps.md` | — | each gap has evidence and a feasible design |
| 10 | Delivery & QA | chat cards, `10_report.*`, `10_figures/`, `10_qa_log.md`, workbook | `study_cards.py chat`, `build_report.py`, `format_references.py`, `audit_citations.py`, `export_workbook.py` | all audits pass |

Keep the `Status:` line in `00_protocol.md` current (e.g. `Status: Stage 6 — 18/29 cards`).
When the user says "continue", read it and resume there.

---

## 5. Stages 0–2: protocol, evidence scan, search strategy

**Stage 0 — Protocol.** Turn the request into a main question plus sub-questions on
**mechanism**, **magnitude**, **heterogeneity** (where, when, for whom) and **method** (does
identification change the answer?). Fill `00_protocol.md`: intake answers, the window, PECO,
inclusion (I…) and exclusion (E1–E7) criteria, literature types (journals plus working papers —
NBER, CEPR, BIS, IMF, ECB, Fed, central banks — labeled `PREPRINT`), the search routes, the
stopping rule and the deliverable. → **C1**

**Stage 1 — Evidence scan and seeds.** Find systematic reviews, meta-analyses, JEL/JES/Handbook
surveys and central-bank or IFI overviews; verify them (§8) and log type, search end date, scope,
conclusion and how this review builds on them in `01_evidence_scan.md`. Pick **5–15 seed papers
published inside the window** into `01_seeds.csv`; they test the search's recall.

**Stage 2 — Search strategy.** Split the question into 2–4 concept blocks; list synonyms,
spellings, acronyms, translations and JEL codes. Write one Boolean master string per block
combination and translate it for every database:

```bash
python3 scripts/search_sources.py --print-queries --query '("phillips curve" OR "inflation dynamics") AND (regime* OR "markov switching") AND ("geopolitical risk" OR "climate risk")'
```

Plan rows in `02_search_log.csv` for every route × string × language. Where to search:
`references/sources.md` (catalog, regional packs, working-paper series) and
`references/source-access.md` (how to reach each database).

---

## 6. Stage 3 — Search through every available route

Use every route the session offers (`references/source-access.md` §1):

- **A. API scripts** — the systematic backbone when the shell has network access:
  ```bash
  python3 scripts/search_sources.py litrev-<slug>/ --query '…' \
      --sources openalex,crossref,semanticscholar,arxiv[,scopus,sciencedirect,wos,scholar] --max 300
  ```
  Scopus and ScienceDirect need an Elsevier key plus institutional access, WoS a Clarivate
  key, Google Scholar a SerpApi key. Exit code 2 = network blocked: use `--dry-run` (prints the
  request URLs for the web fetch tool) and the other routes.
- **B. Research connectors and MCP servers** — Consensus, Elicit, SciSpace and others in the
  session; paper-search-mcp, arxiv-mcp-server, Zotero in Claude Code/Desktop. Run several
  phrasings with the window as a year filter where the tool has one; save results as JSON leads
  and import them. Never call `download_scihub` or `download_with_fallback`.
- **C. Exports** — ask users with library access for WoS, Scopus or ScienceDirect exports and
  Publish or Perish (Google Scholar) CSVs, with the printed query strings (or, with their
  approval, run the query and press Export in their logged-in session through a browser
  extension — one export per query, no scraping):
  ```bash
  python3 scripts/import_records.py litrev-<slug>/ savedrecs.txt scopus.csv consensus.json --query "…"
  ```
- **D. Web search + web fetch** — working-paper and policy series and regional sources by
  domain-filtered search (`nber.org`, `bis.org`, `imf.org`, `ecb.europa.eu`, `tcmb.gov.tr`,
  `ideas.repec.org`, `dergipark.org.tr`, …); fetch paper pages, not search pages.
- **Snowballing** — backward (reference lists, OpenAlex `referenced_works`) and forward
  (Semantic Scholar citations) from the core set; author chasing; log each round (`S1`, `S2`,
  source `snowball-backward/forward`). Add a **recency sweep** for the last 18 months.

Then:

```bash
python3 scripts/dedupe_records.py litrev-<slug>/    # merges part files, removes duplicates, flags WP↔journal pairs
python3 scripts/coverage_check.py litrev-<slug>/    # seed recall + saturation
```

A working paper and its journal version are one study with two reports: cite the journal
version and count one study. If `coverage_check.py` fails, add queries (synonyms, routes,
languages, another snowball round) and rerun; do not move on while it fails unless you record
why in the protocol (e.g. a database the user cannot access).

---

## 7. Stage 4 — Screening

```bash
python3 scripts/screening_check.py window litrev-<slug>/    # outside the window -> exclude, E7
```

Then screen titles/abstracts and full texts against the criteria; record each decision and
code in `04_screening.csv` (stage `ta`/`ft`; include, exclude, maybe, not_retrieved). Keep prior
reviews out of the included set (E6) but mine their reference lists. Online-first articles that
straddle the window boundary may be re-included with a note.

**Consistency check** — the substitute for a second human screener:

```bash
python3 scripts/screening_check.py sample litrev-<slug>/ --n 40
# re-screen 04_rescreen.csv blind from the protocol alone — ideally a separate agent
python3 scripts/screening_check.py compare litrev-<slug>/
python3 scripts/prisma_flow.py litrev-<slug>/ --lang tr
```

Kappa below 0.60: clarify the criterion behind the disagreements, re-screen, note the change.
The PRISMA flow reports window exclusions as removed before screening. → **C2**: counts by
stage, included studies by theme, the number of cards that will follow.

---

## 8. Stage 5 — Verification

Every included study and every source the report cites gets three checks: **A** an
authoritative record that passes the match test, **B** the printed link resolves, **C**
integrity (retraction, front matter, peer-review status, version). Work in batches of 5–10 and
write each batch to `05_verification.csv`. Connector and Google Scholar leads always go through
this ladder; their links are never printed.

### 8.1 Ladder — stop at the first rung that matches

| Rung | Source | How | Confidence |
|---|---|---|---|
| 1 | DOI record | Crossref `https://api.crossref.org/works/{DOI}` or OpenAlex `https://api.openalex.org/works/doi:{DOI}` | High |
| 2 | Official landing page | publisher or series page (NBER, BIS, IMF, ECB, Fed, World Bank, OECD, central banks, DergiPark/SciELO article page); title and authors match | High |
| 3 | Index page | `ideas.repec.org` paper page, Semantic Scholar API, SSRN abstract page | Medium–High |
| 4 | Search snippet only | metadata seen only in a result list | at most `PARTIAL`, never load-bearing |
| — | nothing matched | — | `NOT_VERIFIED` |

### 8.2 Link check

DOI: `https://doi.org/api/handles/{DOI}` returns `responseCode: 1` and the target for a
registered DOI, HTTP 404 otherwise; a successful Crossref or OpenAlex fetch by that DOI also
counts. No DOI: fetch the URL; it counts only if the page loads and shows the title. Prefer DOI
→ publisher or series page → repository page; never print a search-results page, a Google
Scholar or connector link, or a shadow-library link. Record `link`, `link_check_method`,
`checked_on`.

### 8.3 Match test — all four must hold

(1) Title substantively identical; (2) first-author surname identical, allowing diacritics and
particles; (3) year within ±1 with the reason recorded (online-first vs. issue year; WP vs.
journal) — print the issue year of the version of record; (4) venue consistent or the
difference explained. Free-text finders always return *something*; a near-miss is a failure.

### 8.4 Integrity and transport facts

`is_retracted` / a Crossref retraction relation → `RETRACTED` (drop it, re-check claims that
leaned on it); `is_paratext` → not evidence; working papers → `PREPRINT` and look for the
published version; unfamiliar venues → the predatory-venue signals in `references/sources.md`.
Registry quirks (online-first years in Crossref `issued`, flattened bylines, rate limits,
blocked shells) are listed in `references/sources.md` §1 and `references/source-access.md` §3.
The publisher's byline wins over registry author lists — fetch it before formatting (APA lists
up to 20 authors). `scripts/verify_refs.py` automates rung 1 and the link check where the shell
has network.

### 8.5 Failure thresholds

More than 20% `NOT_VERIFIED` → say so prominently, before the findings. More than 50% → stop,
diagnose (rate limits, grey literature, bad input) and ask how to proceed. If registries are
unreachable, say so — never fall back on memory.

---

## 9. Stage 6 — Full texts and study cards (three passes)

Read `references/study-cards.md` first. In short:

```bash
python3 scripts/find_fulltext.py litrev-<slug>/          # legal open-access copies (Unpaywall, OpenAlex, S2)
python3 scripts/study_cards.py init litrev-<slug>/       # one 'todo' card per included study in the window
```

For **every** included study in the window, read the full text where accessible (open copies,
working-paper versions, the user's library through Zotero or uploads) and fill its card:

1. **Pass 1 — Abstract → Conclusion:** question, sample, method, main result (sign, size,
   units), what the conclusion claims and whether the evidence supports it.
2. **Pass 2 — Introduction → Methodology:** claimed contribution, specification, identification,
   data and transformations, estimation, inference, robustness.
3. **Pass 3 — Literature review:** strands and key works it builds on, the gap it claims, what
   it does not engage with.
4. **NE YAPMIŞ? / WHAT DID IT DO?** — one paragraph: question → data → method → finding →
   contribution.
5. **NEYİ EKSİK BIRAKMIŞ? / WHAT DID IT LEAVE OUT?** — variables, channels, countries, periods,
   frequencies and methods not covered, against the literature and the user's question; the
   authors' own future-work list.
6. **Weaknesses** — at least one per study in `06_weaknesses.csv`: category (10-category
   taxonomy), severity (high / medium / low), basis (author-stated / reviewer-identified) and
   the location that shows it.
7. **Relevance** — how the study serves the user's own work.

Abstract-only studies get `[AB]` cards: pass 1 only, claims "according to its abstract",
weaknesses only where the abstract shows them (otherwise the note "weaknesses not assessable
from the abstract"). Code the synthesis fields in
`06_extraction.csv` (theme, country, method family, direction and magnitude with units and
location — `references/econ-methods.md`) and comparable estimates in `06_estimates.csv`.

```bash
python3 scripts/study_cards.py check litrev-<slug>/      # must PASS before delivery
python3 scripts/study_cards.py stats litrev-<slug>/ --lang tr
```

**Stage 7 — Appraisal.** Score credibility 0–2 on identification, data, inference,
robustness, transparency and relevance (`references/econ-methods.md`), consistent with the
weaknesses recorded. Record venue indicators separately with source and date; venue is context,
not evidence.

---

## 10. Stage 8 — Synthesis and answers

Read `references/synthesis.md` before writing. In short:

- **Organize by argument, not by author.** For each theme: claim → supporting and opposing
  studies → direction and magnitude range with units → heterogeneity explained by method,
  sample, period or identification → weighting by credibility → calibrated verdict.
- **Use the cards.** Recurring weaknesses lower certainty or explain disagreement; say which
  studies avoid them (synthesis §6).
- **Quantitative synthesis** when ≥ 10 comparable estimates exist:
  `python3 scripts/meta_analysis.py litrev-<slug>/ --by outcome` (add `--pcc` for partial
  correlations). Report per MAER-NET (Havránek et al., 2020); never pool different units.
- **Publication bias is the default suspicion in economics** (Ioannidis et al., 2017;
  Brodeur et al., 2020): say what bias-corrected estimates do to the answer.
- **Answer every research question** (synthesis §1): answer, magnitude, certainty (High /
  Moderate / Low / Very low) with reasons, evidence base, where the answer changes.

Write `08_synthesis.md` with every claim tagged. → **C3**

---

## 11. Stage 9 — Research gaps

Classify each gap — context (countries, periods, frequencies), method (identification,
non-linearity, regime dependence, time variation), mechanism, data/measurement, unresolved
contradiction, policy relevance. Start from the cards: repeated "left out" items and
high-severity weaknesses that no study fixes. Each gap needs (a) evidence that it is open — the
dated searches that found nothing, or the named conflicting studies — and (b) a feasible design
(data, identification, method). Say "this search found no…", never "the literature has
never…". Rank by importance × feasibility in `09_gaps.md`.

---

## 12. Stage 10 — Delivery, report and QA

Read `references/reporting.md`.

### 12.1 In the chat (always)

1. **Answers** to each research question with certainty and card numbers.
2. **The corpus at a glance** — window, routes and databases searched, counts, verification.
3. **Every study card**, by theme, in batches until all are shown:
   ```bash
   python3 scripts/study_cards.py chat litrev-<slug>/ --lang tr --batch 8 --part 1   # then --part 2, 3, …
   ```
4. **Weakness patterns and research gaps.**
5. Files delivered and one next step.

### 12.2 Illustrated report (when requested: DOCX, PDF or both)

Write the narrative into the `10_report.md` skeleton, keeping its placeholders
(`{{FIGURE:prisma}}`, `{{FIGURE:years}}`, `{{FIGURE:map}}`, `{{FIGURE:weaknesses}}`,
`{{CARDS}}`, `{{REFERENCES}}`, …), then:

```bash
python3 scripts/build_report.py litrev-<slug>/ --format both --lang tr --toc --title "…" --author "…"
```

It draws the figures, builds the DOCX (pandoc with a styled template, or python-docx) and the
PDF (LibreOffice). Render the PDF pages to images and look at them before sending.

### 12.3 References and audits

```bash
python3 scripts/format_references.py litrev-<slug>/05_verification.csv --lang tr > refs.md
python3 scripts/audit_citations.py litrev-<slug>/10_report_full.md litrev-<slug>/05_verification.csv
python3 scripts/export_workbook.py litrev-<slug>/
```

The reference list is built from verified metadata, never retyped. The audit fails on in-text
citations without a verified entry, citations of `NOT_VERIFIED`/`RETRACTED` sources and entries
without a checked link — fix every flag. **Claim audit**: re-open the source for 10% of `[FT]`
claims (at least 5), every headline number and every high-severity weakness; log in
`10_qa_log.md`. For high-stakes work, a separate agent that has not seen the drafting does it.
Close with the summary in templates §8 (window, cards, answers, verification, links, search,
limitations, files).

### 12.4 Update mode (living review)

For an existing folder: read `00_protocol.md` and `02_search_log.csv`; rerun every logged query
for dates after the last search (three months' overlap); log new runs with new ids; dedupe;
screen, verify and card only the new records; rerun the meta-analysis; report what changed —
new studies, changed answers or certainty, new gaps — with an updated PRISMA flow.

---

## 13. Methodological anchors (verified)

Full APA 7 entries are in `references/methodological_anchors.md`; copy them from there.

| Short citation | Use it for | Link |
|---|---|---|
| Page et al. (2021) — PRISMA 2020 | reporting the review | https://doi.org/10.1136/bmj.n71 |
| Rethlefsen et al. (2021) — PRISMA-S | reporting the search | https://doi.org/10.1186/s13643-020-01542-z |
| Tricco et al. (2018) — PRISMA-ScR | scoping reviews | https://doi.org/10.7326/M18-0850 |
| Wohlin (2014) | snowballing procedure | https://doi.org/10.1145/2601248.2601268 |
| Keshav (2007) | multi-pass reading of a paper | https://doi.org/10.1145/1273445.1273458 |
| Cohen (1960) | kappa for screening consistency | https://doi.org/10.1177/001316446002000104 |
| Guyatt et al. (2008) — GRADE | certainty of evidence | https://doi.org/10.1136/bmj.39489.470347.AD |
| Havránek et al. (2020) — MAER-NET | meta-analysis reporting in economics | https://doi.org/10.1111/joes.12363 |
| Iršová et al. (2024) | practitioner's guide to meta-analysis | https://doi.org/10.1111/joes.12595 |
| Stanley & Doucouliagos (2014) | FAT–PET–PEESE | https://doi.org/10.1002/jrsm.1095 |
| DerSimonian & Laird (1986) | random-effects estimator | https://doi.org/10.1016/0197-2456(86)90046-2 |
| Higgins & Thompson (2002) | I² heterogeneity | https://doi.org/10.1002/sim.1186 |
| Andrews & Kasy (2019) | selection-model correction | https://doi.org/10.1257/aer.20180310 |
| Ioannidis et al. (2017) | power and bias in economics | https://doi.org/10.1111/ecoj.12461 |
| Brodeur et al. (2020) | p-hacking by method | https://doi.org/10.1257/aer.20190687 |

Re-verify any source you add, methodological ones included.

---

## Bundled files

- `references/source-access.md` — routes and access for WoS, Scopus, ScienceDirect, Google Scholar, Semantic Scholar, OpenAlex, Crossref, arXiv, Consensus, Elicit, SciSpace and MCP servers; query translation; import formats. Stages 2–3, 6.
- `references/study-cards.md` — three-pass reading, what it did / left out, weakness taxonomy, chat card format. Stage 6.
- `references/reporting.md` — chat delivery order, report skeleton and placeholders, figures, DOCX/PDF build. Stage 10.
- `references/sources.md` — source catalog, working-paper series, regional packs, journal sets, venue quality, predatory signals. Stages 1–3, 7.
- `references/econ-methods.md` — extraction fields, estimates file, method taxonomy, credibility rubric. Stages 6–7.
- `references/synthesis.md` — answer format, certainty grading, meta-analysis, evidence map, weakness patterns. Stage 8.
- `references/templates.md` — intake messages, file schemas, checkpoints, report outlines, methods wording. Intake, Stages 0, 4, 10.
- `references/methodological_anchors.md`, `references/example_verification.csv` — verified anchors and a worked verification log.
- `scripts/` — `init_review.py`, `search_sources.py`, `import_records.py`, `dedupe_records.py`, `coverage_check.py`, `screening_check.py`, `prisma_flow.py`, `verify_refs.py`, `find_fulltext.py`, `study_cards.py`, `meta_analysis.py`, `make_figures.py`, `build_report.py`, `format_references.py`, `audit_citations.py`, `export_workbook.py` (shared helpers in `litrev_common.py`).
