# Contributing

Contributions are welcome. The project is governed by one principle: **nothing unverified enters
the skill.** A reference, a URL pattern or an access note is added only after it has been checked,
and the check is recorded.

## Ways to contribute

- **Regional source packs** for
  [`sources.md`](skills/econ-finance-lit-review/references/sources.md): national journal
  platforms, central-bank series and thesis repositories. Mark each access note
  `*tested YYYY-MM-DD*` and state how it was tested (web search, web fetch, API or browser).
- **Import formats and source adapters** for `scripts/import_records.py` and
  `scripts/search_sources.py` (for example, EconLit, CNKI, KCI or TR Dizin exports), each with a
  mocked test and a dated note in
  [`source-access.md`](skills/econ-finance-lit-review/references/source-access.md).
- **Template translations** for `references/templates.md` and `references/synthesis.md`
  (checkpoint messages, report skeletons, calibrated phrasing).
- **Worked examples for the weakness taxonomy** in further fields of economics and finance
  ([`study-cards.md`](skills/econ-finance-lit-review/references/study-cards.md)).
- **Verification failure reports**: any review in which a fabricated, mismatched or retracted
  reference passed the checks, a link did not resolve, or a stage was skipped. Please use the
  *Verification failure* issue form and include the prompt, the environment (Claude app, Claude
  Code or API) and the relevant rows of `05_verification.csv`.
- **Script improvements**, accompanied by tests.

## Adding or changing references inside the skill

1. Retrieve the registry record (Crossref or OpenAlex, by DOI) and, for author lists, the
   publisher's byline.
2. Add the row to `references/example_verification.csv` with `status`, `method`,
   `link_check_method`, `checked_on` and, where relevant, `discrepancy_note`.
3. Regenerate the formatted list and update `references/methodological_anchors.md`:

   ```bash
   python skills/econ-finance-lit-review/scripts/format_references.py \
       skills/econ-finance-lit-review/references/example_verification.csv
   ```

## Development setup

```bash
python -m pip install numpy matplotlib openpyxl python-docx pyyaml pytest
python -m pytest -q                     # report tests also use pandoc and LibreOffice if installed
python tools/build_skill_zip.py         # dist/econ-finance-lit-review.zip
python tools/make_readme_figures.py     # regenerate the README figures after editing the generator
claude plugin validate .                # requires Claude Code
```

`SKILL.md` must remain under 500 lines and its description under 1,024 characters; the test suite
checks both. When adding an instruction to the skill, state the reason for the rule rather than
relying on emphasis: the model applies rules more consistently when their purpose is explained.

## Pull requests

- [ ] The test suite passes (`python -m pytest -q`).
- [ ] New sources and access notes are marked as tested, with a date.
- [ ] Every added reference was verified against a registry record; none was added from memory.
- [ ] No API keys, tokens or licensed full texts are included.
- [ ] `CHANGELOG.md` is updated.

## Release procedure

1. Update the version in the `SKILL.md` metadata, `.claude-plugin/plugin.json`, `CITATION.cff`
   and the README (version badge and BibTeX entry), and add a `CHANGELOG.md` entry.
2. Tag the release commit: `git tag v2.0.0 && git push --tags`.
3. Run `python tools/build_skill_zip.py` and attach `dist/econ-finance-lit-review.zip` to the
   GitHub release.

## Questions and conduct

Questions and proposals are welcome in the
[issue tracker](https://github.com/ibrahimongoren/econ-finance-lit-review/issues).
Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md); security
issues should be reported privately as described in the [security policy](SECURITY.md).
