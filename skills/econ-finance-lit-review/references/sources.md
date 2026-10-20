# Source catalog for economics and finance reviews

Read at Stages 1–3 (where to search) and Stage 7 (journal quality). How to reach each
database — APIs, keys, connectors, MCP servers, exports — is in `source-access.md`; this file
is the catalog. Notes marked *tested 2026-10-08* come from a sandboxed session using web
search and web fetch tools; other environments may behave differently, so log anything that
does.

## Contents
1. Registries and discovery APIs
2. Field indexes and aggregators
3. Working-paper and policy series
4. Regional source packs
5. Journal sets for sanity checks
6. Journal quality and venue screening
7. Predatory-venue signals

---

## 1. Registries and discovery APIs

| Source | Use | Endpoint / pattern | Access notes |
|---|---|---|---|
| Crossref | DOI metadata, retraction relations, reference lists | `https://api.crossref.org/works/{DOI}` | *tested*: works by web fetch; HTTP 429 after ~8 rapid calls. `issued` is the earliest (often online-first) date; the issue year is in `published-print`. Free-text `works?query.bibliographic=` returned unrelated records for an exact title + authors — weak finder. Splits some compound surnames wrongly. |
| OpenAlex | search (`search_sources.py`) and enrichment: `is_retracted`, `is_paratext`, `cited_by_count`, `open_access.oa_url`, `referenced_works`, `abstract_inverted_index` | `https://api.openalex.org/works/doi:{DOI}` | *tested*: path form works; `works?search=` returned 429 via web fetch. Searches count against a daily budget that a free key raises (checked 2026-10-19). Flattens consortium bylines and can drop middle initials. |
| doi.org handle API | does the DOI resolve, and where | `https://doi.org/api/handles/{DOI}` | *tested*: registered DOI → `responseCode: 1` + target URL; unregistered → HTTP 404. |
| Semantic Scholar | forward citations, external IDs | `https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}?fields=title,year,venue,citationCount,externalIds`; citations: `/paper/DOI:{DOI}/citations` | *tested*: works; `year` may be the first (working-paper) version's year. |
| Research connectors | discovery, abstracts, sometimes full text | Consensus, Elicit, SciSpace or others if connected | *tested 2026-10-20*: Consensus free plan returned 10 results, no DOI; Elicit tools need a Pro or higher plan; SciSpace has no year filter. Leads only — every record goes through verification. Follow each connector's own rules when quoting its results (`source-access.md` §6). |

## 2. Field indexes and aggregators

- **RePEc / IDEAS** (`ideas.repec.org`) — the economics index, strongest on working
  papers. *Tested*: search pages robots-blocked for web fetch; paper pages open.
  Discover with domain-filtered web search, then fetch the paper page.
- **EconBiz** (`econbiz.de`, run by ZBW – Leibniz Information Centre for Economics) —
  economics search portal with strong European and German-language coverage.
  *Tested*: the site's bot protection blocked web fetch; use domain-filtered search.
- **Scopus, Web of Science, ScienceDirect** — through their APIs with the user's keys and
  institutional entitlement, or (more often) through exports the user makes from the web
  interface; import with `import_records.py` (`source-access.md` §4).
- **EconLit** (AEA, via EBSCO and other platforms) — subscription; ask for an RIS export.
- **SSRN** (`papers.ssrn.com`) — preprints; DOIs of the form `10.2139/ssrn.{id}`.
  Treat as `PREPRINT`; look for a published version.
- **Google Scholar** — no API and no automated querying: use SerpApi (paid key) or a
  Publish or Perish export (`source-access.md` §5); "cited by" leads via web search. Never the
  sole source; never print a Scholar link.
- **arXiv** (`econ.EM`, `econ.GN`, `q-fin.*`) — preprints, often with code.
- **CORE** (`core.ac.uk`) — aggregator of open-access research papers from
  repositories; useful for finding full texts. *Tested*: site reachable.
- **BASE** (`base-search.net`, Bielefeld University Library) — open-access search
  engine over repositories. *Tested*: bot protection blocked web fetch.

## 3. Working-paper and policy series

Search with web search restricted to the domain, then fetch the paper page and check
it for a DOI or handle rather than assuming a pattern.

| Series | Domain | Notes |
|---|---|---|
| NBER Working Papers | `nber.org/papers/w{number}` | *tested*: page shows title, authors, date and a `10.3386/w{number}` DOI; it may not mention the later journal version — search for it. |
| CEPR Discussion Papers | `cepr.org` | |
| IZA Discussion Papers | `iza.org` | labor and applied micro |
| BIS Working Papers, Quarterly Review | `bis.org` | BIS also lists central-bank publications at `bis.org/publications/central-bank` |
| IMF Working Papers, Staff Discussion Notes, WEO/GFSR chapters | `imf.org` | |
| ECB Working Paper Series, Occasional Papers, Economic Bulletin | `ecb.europa.eu` | |
| Federal Reserve Board (FEDS, IFDP) and regional Feds | `federalreserve.gov`, `newyorkfed.org`, etc. | |
| World Bank Policy Research Working Papers | `worldbank.org`, `documents.worldbank.org` | |
| OECD Economics Department Working Papers | `oecd.org` | |
| National central banks | each bank's domain | for any country in scope, search its working-paper and research series |
| NGFS | `ngfs.net` | climate scenarios and supervisory work |

## 4. Regional source packs

Add the pack(s) for the countries in scope, search in their languages, and record
each source in the protocol. For any country not listed: its central bank's research
series, its statistics office, its national journal index or platform, and theses.

**Türkiye** (the most thoroughly tested pack)
| Source | Domain | Notes |
|---|---|---|
| DergiPark | `dergipark.org.tr` | *tested*: search pages robots-blocked; domain-filtered web search finds articles; article pages open and show volume/issue/pages and a DOI or a persistent `izlik.org` link. Print the DOI if present, else the article URL. |
| TR Dizin (TÜBİTAK ULAKBİM) | `trdizin.gov.tr` | national journal index; venue status for Turkish journals |
| YÖK Ulusal Tez Merkezi | `tez.yok.gov.tr` | *tested*: interactive search; full texts need login. Use a browser tool if available or ask the user to export results. Cite theses with their number and look for derived articles. |
| TCMB (central bank) | `tcmb.gov.tr` | working papers, research notes, inflation and financial stability reports; publishes *Central Bank Review* |

Search with and without Turkish characters (*parasal aktarım* / *parasal aktarim*).

**Latin America, Spain and Portugal** — SciELO (`scielo.org`; *tested*: Ibero-American
coverage in Portuguese, Spanish and English), Redalyc (`redalyc.org`; article PDFs
indexed by web search, homepage returned 403 to web fetch), CEPAL/ECLAC and national
central banks.

**East Asia** — J-STAGE (`jstage.jst.go.jp`, Japan Science and Technology Agency;
*tested*), KCI – Korea Citation Index (`kci.go.kr`), CNKI for Chinese-language
literature (subscription; ask the user for exports if they have access).

**Africa** — African Journals Online (`ajol.info`; *tested*: non-profit platform for
journals published in Africa), plus national central banks and the African
Development Bank.

**Europe** — EconBiz (above), national central banks and statistical offices,
national-language journals of the countries in scope.

## 5. Journal sets for sanity checks

Not a ranking — a check that the search reaches the venues where a question is
usually published. If no included study comes from the obvious venues, revisit the
strings.

- General interest: American Economic Review, Econometrica, Journal of Political
  Economy, Quarterly Journal of Economics, Review of Economic Studies, Journal of the
  European Economic Association, Economic Journal, Review of Economics and Statistics.
- Macro and monetary: Journal of Monetary Economics, AEJ: Macroeconomics, Journal of
  Money, Credit and Banking, International Journal of Central Banking, Journal of
  International Economics, Journal of Economic Dynamics and Control.
- Econometrics: Journal of Econometrics, Journal of Business & Economic Statistics,
  Journal of Applied Econometrics, Quantitative Economics.
- Finance: Journal of Finance, Journal of Financial Economics, Review of Financial
  Studies, Journal of Financial and Quantitative Analysis, Review of Finance, Journal
  of Banking & Finance, Journal of Financial Intermediation.
- Labor, public, development: Journal of Labor Economics, Journal of Public
  Economics, Journal of Development Economics, World Development, AEJ: Applied and
  AEJ: Economic Policy.
- Environmental and climate: Journal of Environmental Economics and Management,
  Journal of the Association of Environmental and Resource Economists, Energy
  Economics, Review of Environmental Economics and Policy.
- Surveys: Journal of Economic Literature, Journal of Economic Perspectives, Journal
  of Economic Surveys, Annual Review of Economics, Annual Review of Financial Economics.

## 6. Journal quality and venue screening

Report each indicator with **its source, the list's year or edition and the date you
checked**. Never convert between systems and never state a ranking you did not
fetch — write "not verified".

| Indicator | Where | Notes |
|---|---|---|
| SJR quartile | `scimagojr.com` | per subject category and year; a journal can be Q1 in one category and Q2 in another |
| Scopus coverage | Scopus Sources (subscription); discontinued-titles list | discontinued titles are a red flag for later years |
| Web of Science coverage (SSCI, SCIE, ESCI) | `mjl.clarivate.com` | coverage checkable without subscription; JIF needs JCR |
| ABDC Journal Quality List | `abdc.edu.au` | business, finance, economics |
| CABS Academic Journal Guide | `charteredabs.org` | registration needed; report the edition |
| RePEc/IDEAS rankings | `ideas.repec.org/top/` | citation-based, updated monthly |
| DOAJ | `doaj.org` | for open-access journals |
| National indexes | e.g. TR Dizin, KCI, SciELO collections | for national-language journals |

Venue is context, not evidence: a well-identified working paper can outweigh a weakly
identified article in a top journal. Say which you relied on and why.

## 7. Predatory-venue signals

Flag with the specific signal; two or more together justify exclusion or a warning in
the synthesis.

- Not indexed where it claims to be (Master Journal List, Scopus, DOAJ).
- Fake metrics ("Global Impact Factor", "Universal Impact Factor", "Index Copernicus
  value" presented as an impact factor).
- Promised acceptance or review within days; spam solicitation.
- Editorial board that cannot be verified, or members who deny involvement.
- A sudden spike in output; scope far broader than the title.
- Missing ISSN or an ISSN belonging to another title.

Not signals on their own: being new, small, open access with an APC, or published
outside the Anglophone world.
