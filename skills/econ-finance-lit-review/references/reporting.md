# Delivering the review — chat summaries with links, and the illustrated DOCX/PDF report

Read at Stage 10. The chat delivery is always made; the report is made when the user asked for it
at intake (DOCX, PDF or both) or asks later.

## Contents
1. Chat delivery, in order
2. The report: skeleton and placeholders
3. Figures and schemas
4. Building DOCX and PDF
5. Design rules
6. Checks before sending

---

## 1. Chat delivery, in order

1. **Answer first** — each research question answered in 3–6 sentences with its certainty grade
   (`synthesis.md` §1) and the card numbers it rests on: "… [3, 7, 12]".
2. **The corpus at a glance** — window, sources searched (with dates), records → included
   studies, verification tally, how many cards are full-text [FT] and abstract-only [AB].
3. **Every study card**, in batches (`study_cards.py chat --part N`), grouped by theme, each with
   its verified link — until all are shown. Say at the start: "29 çalışma, 4 bölümde".
4. **Weakness patterns and gaps** — the 3–5 recurring weaknesses (with counts from
   `study_cards.py stats`) and the ranked research gaps with a feasible design each.
5. **Files and next step** — the report (if requested), the evidence workbook, the PRISMA figure;
   then one offer (e.g. "Raporu PDF olarak da üreteyim mi?").

Write in the user's language. Never put an unverified source into a card or an answer.

## 2. The report: skeleton and placeholders

`init_review.py` writes `10_report.md`, a skeleton in the protocol language. Replace each HTML
comment with prose (comments are dropped at build time) and keep the placeholders where generated
material belongs:

| Placeholder | Becomes |
|---|---|
| `{{TALLY}}` | the verification tally line |
| `{{FIGURE:pipeline}}` | schema of the review pipeline (stages 0–10) |
| `{{FIGURE:prisma}}` | PRISMA 2020 flow (`prisma_flow.py` must have run) |
| `{{FIGURE:sources}}` | records identified per source |
| `{{FIGURE:years}}` | included studies by year, stacked by method family |
| `{{FIGURE:map}}` | evidence map: themes × method families |
| `{{FIGURE:regions}}` | included studies by country or region |
| `{{FIGURE:weaknesses}}` | weaknesses by category, stacked by severity |
| `{{WEAKNESS_TABLE}}` | the same counts as a table (figures always have a table or labels) |
| `{{CARDS}}` | all study cards (three passes, NE YAPMIŞ? / NEYİ EKSİK BIRAKMIŞ?, weaknesses) |
| `{{REFERENCES}}` | APA 7 list from `05_verification.csv` (hanging indent) |

Captions are numbered automatically ("Şekil 3. …" / "Figure 3. …"). The cover page gets a
key-facts table (window, studies, sources, search dates, verification); `--toc` adds a linked
contents list. Methods-section wording is in `templates.md` §5.

Section order (skeleton): answer in brief → research question and scope → search and selection
→ shape of the literature → findings by theme → weaknesses across the literature → research gaps
→ limitations → study cards → references. For a thesis chapter, add the methods comparison table
from `synthesis.md`; for a policy audience, put a one-page summary before section 1.

## 3. Figures and schemas

`make_figures.py <folder> --lang tr` (called by `build_report.py`) draws PNGs at 200 dpi into
`10_figures/`; a figure whose data are missing is skipped with a message.

| Figure | Data it needs |
|---|---|
| `fig_pipeline` | none (schema) |
| `fig_sources` | `03_records.csv` `source` |
| `fig_years` | cards + `05_verification.csv` year + `06_extraction.csv` `method_family` |
| `fig_map` | card `theme` (or extraction `theme`) + `method_family` |
| `fig_regions` | `06_extraction.csv` `country_region` (comma-separated) |
| `fig_weaknesses` | `06_weaknesses.csv` |
| PRISMA | `prisma_flow.py` → `04_prisma_flow.png` |

Keep `method_family` labels short and consistent (e.g. "Markov-switching", "TVP-VAR", "GMM",
"Local projections", "Quantile", "Machine learning") — they become legend entries.

## 4. Building DOCX and PDF

```bash
python3 scripts/prisma_flow.py litrev-<slug>/ --lang tr
python3 scripts/build_report.py litrev-<slug>/ --format both --lang tr --toc \
    --title "…" --subtitle "Sistematik literatür taraması (2021–2026)" --author "…"
```

Outputs: `10_report.docx` (editable source), `10_report.pdf`, `10_report_full.md` (assembled
Markdown), `10_figures/*.png`.

- **pandoc** (preferred) builds the DOCX with a styled reference document (A4, Calibri,
  navy headings, page numbers, captions, hanging-indent references).
- Without pandoc a built-in python-docx renderer is used (`pip install python-docx`); `--fallback`
  forces it.
- **PDF** comes from LibreOffice (`soffice --headless`, found on PATH or in the usual Windows and
  macOS locations; `--soffice PATH` overrides). Without LibreOffice the DOCX is delivered and the
  user exports the PDF from Word (File › Save As › PDF).
- Check first: `which pandoc soffice; python3 -c "import docx, matplotlib"`. Install what is
  missing when the environment allows (`pip install python-docx matplotlib`).

## 5. Design rules

- One message per figure, stated in its caption; no dual axes; categorical colors in a fixed
  order (the palette in `make_figures.py`), counts labeled on the bars, a table next to any
  figure whose values matter.
- Severity uses one blue ramp (dark = high); never red/green alone to carry meaning.
- Text stays in ink colors; color is for data. Body 10.5 pt, captions 9 pt italic.
- Every number in the text matches the figures and tables; the PRISMA counts match the corpus
  paragraph.

## 6. Checks before sending

1. `study_cards.py check` passes; `audit_citations.py litrev-<slug>/10_report_full.md
   litrev-<slug>/05_verification.csv` passes.
2. Render and look: convert the PDF pages to images (e.g. `pdftoppm -r 60 -png 10_report.pdf p`)
   and view them — cover, a figure page, a card page, the references. Fix overflowing tables,
   empty sections (delete unused headings) and figures without data.
3. Counts agree across the answer, the corpus paragraph, the PRISMA figure and the cards.
4. Send the files (DOCX and/or PDF; the workbook on request) with one line of context each.
