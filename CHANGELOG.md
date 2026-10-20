# Changelog

All notable changes to this project are documented here. The project follows
[Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-10-20

Major revision following field testing: the review now starts from the user's research question,
covers every study in a fixed publication window, reaches the major databases and AI search
engines, and reports each study as a three-pass reading card with its weaknesses.

### Intake and scope
- **Question first, details second**: the skill asks only for a clear research question, then for
  the details (years, variables, data, countries, methods, known papers, database access, output
  format) in one message; answered steps are skipped.
- **Publication window**: the user's years (for example "2020–2026" or "2020–present") or, by
  default, the last five years. `init_review.py --window` writes it to the protocol; every script reads it.
- **New exclusion code E7** (outside the window) and `screening_check.py window`, which applies it
  automatically; PRISMA reports window exclusions as removed before screening.

### Search across databases (new `search_sources.py`, `import_records.py`)
- One Boolean master query translated for OpenAlex, Crossref, Semantic Scholar (bulk syntax),
  arXiv, Scopus, ScienceDirect, Web of Science (Starter API) and Google Scholar (SerpApi);
  `--print-queries` gives the strings for the databases' advanced-search boxes.
- API keys from the environment or a `.env` file (never printed); `--dry-run` prints request URLs
  for the web fetch tool when the shell has no network.
- Imports for Web of Science (tagged and tab-delimited), Scopus CSV, RIS, BibTeX, Publish or
  Perish, Zotero, generic CSV and **JSON from research connectors** (Consensus, Elicit, SciSpace)
  and MCP servers.
- New `references/source-access.md`: routes by environment, endpoints, limits and access rules
  checked in October 2026, connector behavior observed in testing (Consensus free plan: 10 results
  without DOI; Elicit tools need a Pro plan; SciSpace has no year filter), MCP servers.
- New `integrations/` folder: `.mcp.json` and Claude Desktop examples (paper-search-mcp,
  arxiv-mcp-server, zotero-mcp, Elicit, Consensus), a Claude Code permission file that blocks the
  Sci-Hub tools of paper-search-mcp, `.env.example`, optional Python clients.

### Study cards (new `study_cards.py`, `find_fulltext.py`)
- Every included study in the window gets a card: **Pass 1 Abstract → Conclusion, Pass 2
  Introduction → Methodology, Pass 3 Literature review**, then **What did it do?** and **What did
  it leave out?** (Turkish labels: *Ne yapmış?*, *Neyi eksik bırakmış?*) and the study's relevance
  to the user's research.
- **Weakness analysis** with a ten-category taxonomy for economics and finance, severity
  (high/medium/low), basis (author-stated/reviewer-identified) and the location that shows it.
- `study_cards.py check` blocks delivery while a card is incomplete or a weakness is ungrounded;
  `chat` prints the cards in batches with verified links (Turkish or English labels); `stats`
  summarizes weakness patterns for the synthesis.
- `find_fulltext.py` finds legal open-access copies through Unpaywall, OpenAlex and Semantic
  Scholar. Shadow libraries stay forbidden.

### Delivery and report (new `make_figures.py`, `build_report.py`)
- Chat delivery: answers first, corpus at a glance, every card with its link, weakness patterns
  and gaps.
- Illustrated report on request: `10_report.md` skeleton with placeholders, figures (pipeline
  schema, PRISMA, sources, years × method, evidence map, regions, weaknesses), a cover with key
  facts, linked contents, numbered captions, hanging-indent APA references; DOCX through pandoc
  with a styled template (python-docx fallback) and PDF through LibreOffice.
- New `references/study-cards.md` and `references/reporting.md`; intake messages, schemas and
  checkpoints updated in `references/templates.md`; weakness-pattern synthesis in
  `references/synthesis.md`; Keshav (2007) added to the verified anchors.
- Evidence workbook gains Full text, Study cards and Weaknesses sheets.

### Documentation
- README rewritten in an academic layout: abstract, numbered figures and tables, requirements,
  citation metadata and a verified APA reference list. Five figures — pipeline, search
  architecture, three-pass reading, verification, report preview — in light and dark versions,
  generated reproducibly by `tools/make_readme_figures.py`; a test keeps them in sync.
- Professional English documentation throughout (US spelling), a rewritten integrations guide,
  a Code of Conduct, a security policy, GitHub issue forms (verification failure, bug report,
  source or feature request) and a pull request template; tests check README anchors, relative
  links and the issue forms.

### Compatibility
- Review folders from 1.x keep working; run `init_review.py` again in the parent folder to add
  the new files, and add a `Literature window: Y0-Y1` line to the protocol.

## [1.0.0] — 2026-10-08

First public release.

### Pipeline
- Comprehensive, systematic review is the default for any economics or finance topic
  or research question; rapid and update (living review) modes on request.
- Eleven stages (0–10) with a file per stage, so long reviews can pause and resume.
- New stages and checks compared with the internal draft:
  - **Stage 0** turns a bare topic into a main question and sub-questions
    (mechanism, magnitude, heterogeneity, method) and records a stopping rule.
  - **Stage 1** scans prior systematic reviews, meta-analyses and surveys and builds
    a verified seed set.
  - **Stage 3** coverage and saturation check (`coverage_check.py`): seed recall plus
    novelty of the last queries; parallel worker files are merged by
    `dedupe_records.py`.
  - **Stage 4** screening consistency check: blind re-screen of a stratified sample
    and Cohen's kappa (`screening_check.py`).
  - **Stage 8** certainty-graded answers (GRADE-style, adapted to economics) and a
    meta-analysis module (`meta_analysis.py`: fixed and random effects,
    FAT–PET–PEESE, WAAP, moderators, study-clustered SEs, funnel plot).
  - **Stage 10** answer-first report, claim audit, evidence workbook
    (`export_workbook.py`) and update report.
- Checkpoints instead of hard stops: the pipeline asks only when the topic is too broad,
  the user wants an interactive review, or verification fails at scale.

### Verification
- Four-part match test, link checks through the doi.org handle API or the landing
  page, retraction and preprint screening, failure thresholds.
- Access facts from testing documented (rate limits, robots-blocked index pages,
  registry quirks with dates and author lists).
- Fourteen methodological anchors verified against Crossref/OpenAlex (and publisher
  pages where bylines differ).

### Global use
- Output in the user's language; searches in English plus the languages of the
  countries in scope; regional source packs (Türkiye, Latin America and Iberia, East
  Asia, Africa, Europe); English and Turkish templates.
- Citation audit recognizes author-date citations with English, Turkish, Spanish,
  Portuguese, French, German and Italian connectors.

### Distribution
- Claude Code plugin marketplace (`.claude-plugin/`), uploadable ZIP for Claude apps
  (`tools/build_skill_zip.py`), pytest suite and GitHub Actions CI (Python 3.9, 3.11 and 3.13).
