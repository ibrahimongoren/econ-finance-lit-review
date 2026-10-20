# Source access — reaching Web of Science, Scopus, ScienceDirect, Google Scholar, Semantic Scholar, OpenAlex, Crossref, arXiv, Consensus, Elicit and SciSpace

Read at Stages 2–3 (search) and Stage 6 (full texts). Facts marked *checked* were confirmed on
2026-10-19/20 against the providers' documentation, PyPI or a live call; re-check anything that
fails, and log what happened in `02_search_log.csv` notes.

## Contents
1. Pick the routes
2. One strategy, many syntaxes
3. Free scholarly APIs (script: `search_sources.py`)
4. Subscription databases: Scopus, ScienceDirect, Web of Science
5. Google Scholar
6. AI search engines and connectors: Consensus, Elicit, SciSpace
7. MCP servers: paper-search-mcp, arxiv-mcp-server, zotero-mcp
8. Importing results (`import_records.py`) and the JSON lead format
9. Logging, PRISMA and reproducibility
10. Rules

---

## 1. Pick the routes

Probe what the session has (connector tools in the tool list; `python3 scripts/search_sources.py
<folder> --query "test" --sources openalex --max 5` for shell network) and use every route that
works. Comprehensive mode needs at least two independent indexes plus working-paper series and
snowballing.

| Route | When it works | Use for |
|---|---|---|
| **A. API scripts** — `search_sources.py`, `find_fulltext.py` | the shell can reach the APIs: Claude Code, or the Claude desktop app, on a local computer; Claude.ai when the user has allowed the API domains for code execution (paid individual plans: Settings › Capabilities; Team/Enterprise: the organization owner; Free: package managers only) | the systematic backbone: OpenAlex + Crossref + Semantic Scholar (+ arXiv); Scopus, ScienceDirect, WoS, Google Scholar with keys |
| **B. Connectors / MCP** | the tools appear in the session (connectors work regardless of shell egress) | Consensus, Elicit, SciSpace for semantic discovery; paper-search-mcp, arxiv-mcp-server, Zotero |
| **C. Exports** | the user can run the database's web interface (library access) | WoS, Scopus, ScienceDirect, Publish or Perish (Google Scholar): the best route to subscription databases |
| **C′. Browser extension** | Claude in Chrome or the Claude desktop browser is available and the user agrees | Claude runs the printed query in the user's own logged-in WoS/Scopus/ScienceDirect session, sets the years and uses the database's Export button — one export per query; no scraping of result pages, no bulk full-text downloads |
| **D. Web search + web fetch** | always | working-paper and central-bank series, publisher and repository pages; API URLs printed by `--dry-run` |

When route A is blocked (exit code 2), tell the user once which access would open it, then
continue with B–D. Ask for exports from subscription databases at intake when the user has
access (WoS, Scopus, ScienceDirect via their university) — it is the single biggest gain in
coverage for economics.

## 2. One strategy, many syntaxes

Write one Boolean master string per concept-block combination (AND / OR / NOT in capitals,
"quoted phrases", parentheses). The script translates it:

```bash
python3 scripts/search_sources.py --print-queries --query '("phillips curve" OR "inflation dynamics") AND (regime* OR threshold OR "markov switching") AND ("geopolitical risk" OR "climate risk")' --window 2021-2026
```

prints the strings for the Web of Science and Scopus advanced-search boxes (with the year limits
built in), ScienceDirect, Google Scholar/Publish or Perish, Semantic Scholar's bulk syntax
(`+` AND, `|` OR, `-` NOT), OpenAlex, arXiv (`all:` fields, `ANDNOT`) and Crossref (keywords
only — Crossref has no Boolean search). `--q-<source>` overrides one translation. Truncation (`*`)
works in WoS, Scopus and ScienceDirect, not in OpenAlex or Semantic Scholar: add the word forms.

## 3. Free scholarly APIs (route A)

```bash
python3 scripts/search_sources.py litrev-<slug>/ --query '…' \
    --sources openalex,crossref,semanticscholar,arxiv --max 300 [--env-file .env]
```

The window comes from `00_protocol.md`. Each source writes `03_records_part-<Source>.csv` and a
search-log row; `dedupe_records.py` merges them. `--dry-run` prints the first request URL per
source so the web fetch tool can run it when the shell cannot.

| Source | Request (window 2021–2026) | Paging and limits (*checked*) | Key (env var) |
|---|---|---|---|
| OpenAlex | `api.openalex.org/works?search=…&filter=from_publication_date:2021-01-01,to_publication_date:2026-12-31&per_page=100&page=1` | `per_page` ≤ 100; page × per_page ≤ 10,000 (deeper needs cursor paging and a key); searches count against a daily budget that a free key raises | `OPENALEX_API_KEY` (free, `api_key=` parameter) |
| Crossref | `api.crossref.org/works?query.bibliographic=…&filter=from-pub-date:2021-01-01,until-pub-date:2026-12-31&rows=100&cursor=*` | follow `next-cursor`; relevance-ranked over the whole registry, so totals are not topic counts; HTTP 429 after rapid calls | `CONTACT_EMAIL` (polite pool) |
| Semantic Scholar | `api.semanticscholar.org/graph/v1/paper/search/bulk?query=…&year=2021-2026&fields=…` | up to 1,000 per call, continue with `token` | `S2_API_KEY` (free, header `x-api-key`) |
| arXiv | `export.arxiv.org/api/query?search_query=(…)+AND+submittedDate:[202101010000+TO+202612312359]&start=0&max_results=100` | wait 3 s between calls | none |
| Unpaywall | `api.unpaywall.org/v2/{doi}?email=…` | DOI look-up for open-access copies (`find_fulltext.py`) | `UNPAYWALL_EMAIL` or `CONTACT_EMAIL` (required) |

Known behavior: through the web fetch tool, single-work URLs (`/works/doi:…`) worked while
OpenAlex `?search=` URLs failed or were rate-limited; Crossref `issued` is the earliest
(often online-first) date. See `sources.md` §1 for registry quirks used in verification.

## 4. Subscription databases (routes A and C)

**Scopus** (Elsevier). API: `api.elsevier.com/content/search/scopus?query=TITLE-ABS-KEY(…)&date=2021-2026&count=25&start=0&view=STANDARD`
with headers `X-ELS-APIKey` and, off campus, `X-ELS-Insttoken` (*checked*). Needs a key from
dev.elsevier.com **and** the institution's API entitlement (campus IP or VPN, or an institutional
token). The STANDARD view returns the first author only — complete bylines come from Crossref in
Stage 5. Without API access: Scopus web › Advanced document search › paste the printed string ›
select all › Export › CSV (all citation and abstract fields) or RIS.

**ScienceDirect** (Elsevier full-text platform). API: `api.elsevier.com/content/search/sciencedirect?query=…&date=2021-2026&count=100&start=0`
(count 10/25/50/100, start ≤ 6,000; *checked*), same key and entitlement rules. Web: Advanced
search › terms + years › select › Export › RIS or BibTeX. ScienceDirect covers Elsevier journals
only — never a substitute for Scopus or WoS.

**Web of Science** (Clarivate). Starter API: `api.clarivate.com/apis/wos-starter/v1/documents?db=WOS&q=TS=(…) AND PY=(2021-2026)&limit=50&page=1`,
header `X-ApiKey` (*checked*); the free trial plan allows 1 request/s and 50 requests/day, so use
it for small, precise queries. Web: Advanced Search › paste the printed `TS=(…) AND PY=(…)` string
› Export › Plain text file or Tab delimited › Record content: Full record (500 records per file).
Clarivate's Python client: `pip install git+https://github.com/clarivate/wosstarter_python_client.git`.

Import exports with route C (§8). Record the exact query string the user ran.

## 5. Google Scholar

Google Scholar has no API and forbids automated querying; never scrape it, use proxies or solve
CAPTCHAs. Lawful routes:
- **SerpApi** (paid service with a free tier): `serpapi.com/search.json?engine=google_scholar&q=…&as_ylo=2021&as_yhi=2026&num=20&start=0`
  with `SERPAPI_API_KEY` (`--sources scholar`). Results carry no DOI — leads for verification.
- **Publish or Perish** (free desktop app by Anne-Wil Harzing): the user runs the Google Scholar
  query (years set) and saves CSV; it can also query Crossref, OpenAlex, Semantic Scholar, Scopus
  (Elsevier key) and Web of Science (subscription). Import with `import_records.py`.
- Web search restricted to `scholar.google.com` is not a search route; use it only to find
  "cited by" leads, and never print a Scholar link.

## 6. AI search engines and connectors (route B)

Semantic engines find studies that keyword strings miss, but their ranking is not reproducible
and results are capped — use them **in addition to** the Boolean searches, never instead.

| Connector | Call (window 2021–2026) | Observed 2026-10-20 | Notes |
|---|---|---|---|
| **Consensus** | `search(query, year_min=2021)` (add `year_max` only when the window ends before this year); several phrasings (mechanism, method, country) | free plan: 10 results per search, links to consensus.app, no DOI; more per page and DOIs on paid plans | when you show its results directly, follow its display rules (numbered citations with its links, its plan message verbatim) |
| **Elicit** | `search_papers(query, filters={minYear, maxYear}, maxResults)`; keyword mode takes Lucene syntax | API/MCP access needs a Pro or higher plan; otherwise the tool returns `api_access_denied` — tell the user, continue without it | also runs systematic-review and report workflows on paid plans |
| **SciSpace** | `search-papers(searchQuestion)` — a full natural-language question | returns title, authors, date, DOI when known, journal, abstract, URLs; no year filter, older papers appear | apply the window after import (`screening_check.py window`) |
| Others | any scholarly connector the user has | — | same rules |

Workflow: run 3–6 phrasings per connector (main question, each mechanism, each method family,
each country group); save every result as a JSON lead file (§8) — one file per connector and
query — and import it. Every lead goes through Stage 5 verification; a connector link is never a
printed reference.

## 7. MCP servers (route B, Claude Code / Claude Desktop)

Installation commands are in the repository's `integrations/` folder (`mcp.json.example`,
`claude_desktop_config.example.json`). Versions current on PyPI on 2026-10-20.

- **paper-search-mcp 0.1.4** (`uvx paper-search-mcp`): `search_papers` across OpenAlex,
  Crossref, Semantic Scholar, arXiv, CORE, OpenAIRE, SSRN, DOAJ, Zenodo, HAL, Unpaywall and
  others, plus per-source search and download tools. Set `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL`.
  **Never call `download_scihub` or `download_with_fallback`** — in this release the fallback
  tries Sci-Hub by default; use the source-specific download tools (arXiv, Semantic Scholar OA,
  CORE, OpenAIRE, Zenodo, HAL) and `find_fulltext.py`. Do not set its Google Scholar proxy.
- **arxiv-mcp-server 0.8.2** (`uvx arxiv-mcp-server`): search arXiv (econ.EM, econ.GN,
  q-fin), download and read papers section by section.
- **zotero-mcp-server 0.15.1** (`zotero-mcp`, `ZOTERO_LOCAL=true`): search the user's Zotero
  library, read full texts and annotations they hold, add papers by DOI. Good for paywalled
  studies the user's library already provides.

## 8. Importing results (route C) and the JSON lead format

```bash
python3 scripts/import_records.py litrev-<slug>/ savedrecs.txt --query "TS=(…) AND PY=(2021-2026)"
python3 scripts/import_records.py litrev-<slug>/ consensus_q1.json --source Consensus --query "…"
```

Formats are detected from content: RIS, BibTeX, Web of Science tagged text and tab-delimited,
Scopus CSV, Publish or Perish CSV, Zotero CSV, generic CSV, JSON and JSON Lines. Each import adds
`03_records_part-<Source>.csv` and a search-log row (`I<nn>-<PREFIX>`); rows outside the window
are reported and later excluded with `screening_check.py window` (E7).

JSON lead format for connector results (copy fields exactly as the tool returned them; leave a
field out rather than guess it):

```json
[{"title": "…", "authors": ["Given Family", "Given Family"], "year": 2024,
  "doi": "10.xxxx/…", "url": "https://…", "venue": "Journal name", "abstract": "…", "citations": 12}]
```

Raw API or tool payloads also work: SciSpace (`papers`), Semantic Scholar (`data`), OpenAlex
(`results`), Crossref (`message.items`) field names are recognized.

## 9. Logging, PRISMA and reproducibility

- One `02_search_log.csv` row per source × query × date, with the exact string, filters (window,
  document types), hits and retrieved counts. Scripts write these rows; add rows yourself for web
  searches and connector queries you ran without the scripts.
- Databases, APIs, AI search engines and MCP searches count as *databases* in PRISMA; snowballing,
  author chasing, seeds and websites as *other methods* (source names starting with `snowball-`,
  `author`, `seed`, `website`, `user`).
- Note non-reproducible components in the methods: semantic engines change rankings over time;
  report the date, the phrasing and the result caps (e.g. "Consensus, 10 results per query").
- Report every database you could not reach and why (no subscription, plan limits, blocked
  network) under Limitations.

## 10. Rules

- Respect each provider's terms and rate limits; keep the pauses built into the scripts.
- Keys live in environment variables or a local `.env`; never print, log or paste them.
- No shadow libraries, CAPTCHA solving, bot-detection workarounds or Google Scholar scraping.
- Paywalled full texts come from the user's library, the authors, or open versions — nothing else.
