# Integrations

This folder documents how the skill reaches bibliographic databases, AI search engines and
full-text sources, and provides example configuration files. None of the integrations is
required: without keys or servers the skill relies on web search, web fetch and free scholarly
APIs. Endpoint-level details (parameters, limits, query syntax) are maintained in
[`source-access.md`](../skills/econ-finance-lit-review/references/source-access.md).

## 1. Access routes

| Route | Available in | Sources reached |
|---|---|---|
| **A. API scripts** (`search_sources.py`, `find_fulltext.py`) | Claude Code, or the Claude desktop app, on a local computer; Claude apps when code execution is allowed to reach the API domains (Section 5) | OpenAlex, Crossref, Semantic Scholar, arXiv and Unpaywall (free); Scopus and ScienceDirect (Elsevier key and institutional entitlement); Web of Science Starter API (Clarivate key); Google Scholar through SerpApi (paid key) |
| **B. Connectors and MCP servers** | Claude apps (connectors), Claude Code, Claude Desktop | Consensus, Elicit and SciSpace (connectors); paper-search-mcp, arxiv-mcp-server, Zotero (MCP servers) |
| **C. Database exports** (`import_records.py`) | All environments | Web of Science, Scopus, ScienceDirect, Publish or Perish (Google Scholar), Zotero, EndNote, Mendeley — RIS, BibTeX, CSV and Web of Science tagged text |
| **D. Web search and web fetch** | All environments | Working-paper and central-bank series, publisher and repository pages; `search_sources.py --dry-run` prints API request URLs for the web fetch tool |

## 2. Configuration files

| File | Purpose |
|---|---|
| `mcp.json.example` | MCP servers for a Claude Code project. Copy to the project root as `.mcp.json`; variables such as `${CONTACT_EMAIL}` are read from the shell environment. |
| `claude_desktop_config.example.json` | Local (stdio) MCP servers for Claude Desktop. Merge into `claude_desktop_config.json` (Settings › Developer › Edit Config); add Elicit and Consensus as connectors in the application. |
| `claude-code-settings.example.json` | Claude Code permission rules that block the Sci-Hub tools of paper-search-mcp. Merge into `.claude/settings.json`. |
| `.env.example` | Template for the API keys used by the scripts. Copy to `.env` next to the review folder; never commit the completed file. |
| `requirements-sources.txt` | Optional Python clients for the same sources, for interactive work. The skill's scripts do not depend on them. |

## 3. MCP servers and connectors

Status as of October 2026; plan conditions are set by the providers and may change.

| Server | Function | Access and limits |
|---|---|---|
| **Consensus** (connector) | Semantic search over an index built on Semantic Scholar, OpenAlex and PubMed; filters by year, study design and journal quartile | The free plan returns ten results per query, without DOIs; every result is verified in Stage 5 |
| **Elicit** (connector) | Paper search, systematic-review workflows and reports | API and MCP access require an Elicit Pro plan or higher; on other plans the tools return `api_access_denied` |
| **SciSpace** (connector) | Semantic search; returns DOIs where available | No publication-year filter; the review window is applied after import |
| **paper-search-mcp** 0.1.4 | Unified search across OpenAlex, Crossref, Semantic Scholar, arXiv, CORE, OpenAIRE, SSRN, DOAJ, Zenodo, HAL and Unpaywall | Local server; exposes Sci-Hub tools that must be blocked (see the note below) |
| **arxiv-mcp-server** 0.8.2 | arXiv search, download and section-by-section reading (econ.EM, econ.GN, q-fin) | Local server; install from PyPI, as an unrelated npm package uses the same name |
| **zotero-mcp-server** 0.15.1 | Search of the user's Zotero library, full texts and annotations; addition of items by DOI | Local server; gives access to full texts licensed through the user's library |

In the Claude apps, Consensus, Elicit and SciSpace are added from the connector directory. In
Claude Code, the servers are added as follows; the local servers require
[uv](https://docs.astral.sh/uv/).

```bash
# Remote servers (endpoints checked October 2026)
claude mcp add --transport http consensus https://mcp.consensus.app/mcp
claude mcp add --transport http elicit https://elicit.com/api/mcp

# Local servers
claude mcp add --transport stdio --env PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=you@university.edu \
    paper-search -- uvx paper-search-mcp
claude mcp add --transport stdio --scope user arxiv -- uvx arxiv-mcp-server
uv tool install zotero-mcp-server
claude mcp add --transport stdio --env ZOTERO_LOCAL=true zotero -- zotero-mcp
```

For Claude Desktop, run `zotero-mcp setup` instead of the last command, or merge
`claude_desktop_config.example.json`. Zotero must accept local connections: enable *Allow other
applications on this computer to communicate with Zotero* (Zotero › Settings › Advanced).

> **paper-search-mcp and Sci-Hub.** Release 0.1.4 exposes a `download_scihub` tool, and
> `download_with_fallback` attempts Sci-Hub by default. Block both tools with
> `claude-code-settings.example.json` or disable them in the client; the skill never calls them.
> Do not configure a proxy to circumvent Google Scholar's bot detection.

## 4. API keys

| Variable | Service | Registration | Conditions |
|---|---|---|---|
| `CONTACT_EMAIL`, `UNPAYWALL_EMAIL` | Crossref (polite pool), Unpaywall | Any valid address | Required by Unpaywall |
| `OPENALEX_API_KEY` | OpenAlex | openalex.org/settings/api (free) | Searches draw on a daily budget; a key raises it |
| `S2_API_KEY` | Semantic Scholar | semanticscholar.org/product/api (free) | Optional; increases the rate limit |
| `ELSEVIER_API_KEY`, `ELSEVIER_INSTTOKEN` | Scopus, ScienceDirect | dev.elsevier.com | Requires the institution's API entitlement; requests must originate from the campus network or VPN, or carry an institutional token |
| `WOS_API_KEY`, `WOS_DB` | Web of Science Starter API | developer.clarivate.com | Free trial plan limited to 1 request per second and 50 requests per day; institutional plans offer more |
| `SERPAPI_API_KEY` | Google Scholar via SerpApi | serpapi.com (paid; limited free tier) | Google Scholar offers no official API; results carry no DOI |

## 5. Network access in Claude apps

In the Claude apps the scripts run in the code-execution sandbox, whose internet access is
configured in the web application: on paid individual plans under **Settings › Capabilities**, and
on Team and Enterprise plans by the organization owner under **Organization settings ›
Capabilities**. The Free plan permits package managers only. To let the scripts call the APIs,
allow `api.openalex.org`, `api.crossref.org`, `api.semanticscholar.org`, `export.arxiv.org`,
`api.unpaywall.org` and `doi.org`, and — where keys are available — `api.elsevier.com`,
`api.clarivate.com` and `serpapi.com`. Connectors operate independently of this setting; without
network access the skill relies on connectors, web fetch and database exports.

## 6. Exports from subscription databases

Exports are the most reliable route to subscription databases and require no API access.

| Database | Export procedure | Format |
|---|---|---|
| Web of Science | Export › Plain text file or Tab delimited; record content *Full record* (up to 500 records per file) | Tagged text or tab-delimited |
| Scopus | Export › CSV (all citation and abstract fields) or RIS | CSV or RIS |
| ScienceDirect | Select results › Export › RIS or BibTeX | RIS or BibTeX |
| Google Scholar | Publish or Perish (free desktop application) › Save as CSV | CSV |
| Consensus, Elicit, SciSpace | Results saved by the skill during the search | JSON |

Each file is imported together with the exact query that produced it; the query is recorded in
`02_search_log.csv` for the methods section and PRISMA-S reporting.

```bash
python3 scripts/import_records.py litrev-<topic>/ savedrecs.txt \
    --query "TS=(…) AND PY=(2021-2026)"
python3 scripts/import_records.py litrev-<topic>/ scopus.csv \
    --query "TITLE-ABS-KEY(…) AND PUBYEAR > 2020"
python3 scripts/import_records.py litrev-<topic>/ sciencedirect.ris \
    --source ScienceDirect --query "…"
python3 scripts/import_records.py litrev-<topic>/ pop.csv --query "…"
python3 scripts/import_records.py litrev-<topic>/ consensus.json \
    --source Consensus --query "…"
```

`search_sources.py --print-queries --query '…'` translates the Boolean master query into the
advanced-search syntax of each database, so that exports and API searches follow the same
strategy.

## 7. Browser extensions

- **Claude in Chrome**, or the browser built into the Claude desktop application, can run the
  printed query in the user's authenticated Web of Science, Scopus or ScienceDirect session, set
  the publication years and use the database's own export function — one export per query and
  only with the user's approval. Result pages are not scraped and full texts are not downloaded
  in bulk, as institutional licenses prohibit systematic downloading.
- **Zotero Connector** saves items, together with any PDFs licensed through the user's library,
  to Zotero; with zotero-mcp the skill can then read them for the three-pass study cards.

## 8. Acceptable use

The skill does not use shadow libraries (Sci-Hub, LibGen or their mirrors), circumvent CAPTCHAs
or bot detection, scrape Google Scholar, redistribute licensed full texts or display API keys.
Paywalled studies are obtained through the user's library or from the authors.
