"""Synthetic review data for tests. Every author, title and DOI here is fictional (DOI prefix 10.5555 is
Crossref's test prefix); nothing in this file is a real reference."""

from __future__ import annotations

from pathlib import Path

from litrev_common import FILES, HEADERS, write_csv

THEMES = ["Expectations and persistence", "Oil and exchange-rate pass-through", "Geopolitical risk",
          "Climate risk", "Regime switching"]
METHODS = ["Markov-switching", "TVP-VAR", "GMM", "Local projections", "Machine learning", "Quantile regression"]
COUNTRIES = ["Turkey", "Brazil", "Mexico", "South Africa", "OECD panel", "Euro area"]
SOURCES = ["OpenAlex", "Crossref", "SemanticScholar", "Scopus", "WebOfScience", "snowball-backward"]
FAMILIES = ["Doe", "Roe", "Smith", "Kaya", "Silva", "Novak", "Okafor", "Lindqvist", "Moreau", "Tanaka",
            "Yilmaz", "Costa"]
WEAK = [
    ("identification", "high", "Expected inflation is treated as exogenous; no instrument for survey expectations.",
     "Section 3.2", "reviewer-identified"),
    ("data_measurement", "medium", "Climate risk index is annual and interpolated to quarterly frequency.",
     "Data appendix", "author-stated"),
    ("robustness", "medium", "Regime count fixed at two; no test against three regimes.", "Table 4",
     "reviewer-identified"),
    ("external_validity", "low", "Single-country sample limits generalization to other emerging markets.",
     "Conclusion", "author-stated"),
    ("estimation_inference", "high", "Weak-instrument diagnostics are not reported for the GMM estimates.",
     "Table 2", "reviewer-identified"),
    ("literature_positioning", "low", "Does not engage with recent nonlinear Phillips-curve evidence.",
     "Section 2", "reviewer-identified"),
]


def build_demo(folder: Path, n: int = 12, y0: int = 2021) -> list[str]:
    """Fill an initialized folder with n included synthetic studies (years y0..y0+5) plus noise records."""
    records, log, screening, ver, ext, cards, weak, ft = [], [], [], [], [], [], [], []
    for q, src in enumerate(SOURCES, 1):
        log.append({"query_id": f"Q{q}", "date": "2026-10-01", "source": src, "query_string": "phillips curve",
                    "filters": f"{y0}-{y0 + 5}", "hits": "40", "retrieved": "40"})
    ref_ids = []
    for i in range(n):
        rid, ref = f"R{i + 1:03d}", f"S{i + 1:02d}"
        year = y0 + (i % 6)
        fam = FAMILIES[i % len(FAMILIES)]
        authors = f"{fam}, Alex" + ("; Second, Sam" if i % 3 == 1 else "") + ("; Third, Tom" if i % 3 == 2 else "")
        title = f"Synthetic study {i + 1} on a regime-dependent hybrid Phillips curve"
        doi = f"10.5555/demo.{i + 1:03d}"
        records.append({"record_id": rid, "source": SOURCES[i % len(SOURCES)], "query_id": f"Q{i % 6 + 1}",
                        "title": title, "authors": authors, "year": str(year), "venue": "Journal of Testing",
                        "doi": doi, "type": "journal-article"})
        screening += [{"record_id": rid, "stage": "ta", "decision": "include"},
                      {"record_id": rid, "stage": "ft", "decision": "include"}]
        ver.append({"ref_id": ref, "record_id": rid, "status": "PREPRINT" if i == 5 else "VERIFIED",
                    "confidence": "high", "method": "crossref", "link": f"https://doi.org/{doi}",
                    "link_check_method": "doi.org handle API", "checked_on": "2026-10-02", "authors": authors,
                    "year": str(year), "title": title, "venue": "Journal of Testing", "volume": str(10 + i),
                    "issue": "1", "pages": f"{i + 1}-{i + 20}", "doi": doi,
                    "type": "working-paper" if i == 5 else "journal-article",
                    "series": "Test WP Series" if i == 5 else "", "number": "5" if i == 5 else ""})
        ext.append({"ref_id": ref, "theme": THEMES[i % len(THEMES)], "country_region": COUNTRIES[i % len(COUNTRIES)],
                    "method_family": METHODS[i % len(METHODS)], "evidence_level": "FT" if i % 4 else "AB"})
        level = "AB" if i % 4 == 0 else "FT"
        cards.append({"ref_id": ref, "theme": THEMES[i % len(THEMES)],
                      "pass1_abstract_conclusion": "Asks whether inflation persistence differs across regimes; "
                                                   "finds higher persistence in the high-risk regime.",
                      "pass2_intro_method": "" if level == "AB" else "Two-regime Markov-switching hybrid NKPC, "
                                                                     "quarterly data, survey expectations.",
                      "pass3_literature": "" if level == "AB" else "Builds on hybrid NKPC work; positions against "
                                                                   "linear GMM estimates.",
                      "what_it_did": "Estimates a regime-dependent hybrid Phillips curve with a risk index.",
                      "what_it_left_out": "No climate-risk channel; no out-of-sample comparison.",
                      "relevance": "Direct benchmark for the user's regime-dependent specification.",
                      "full_text_source": "" if level == "AB" else f"https://doi.org/{doi}",
                      "evidence_level": level, "card_status": "checked"})
        for k in range(1 + i % 3):
            cat, sev, text, loc, basis = WEAK[(i + k) % len(WEAK)]
            weak.append({"ref_id": ref, "category": cat, "severity": sev, "weakness": text,
                         "evidence_location": "abstract" if level == "AB" else loc, "basis": basis})
        ft.append({"ref_id": ref, "doi": doi, "oa_url": f"https://doi.org/{doi}" if level == "FT" else "",
                   "oa_source": "OpenAlex" if level == "FT" else "", "checked_on": "2026-10-02"})
        ref_ids.append(ref)
    # noise: two excluded records and one outside the window
    for j, (year, code) in enumerate([(y0 + 1, "E1"), (y0 + 2, "E3")]):
        rid = f"X{j + 1:03d}"
        records.append({"record_id": rid, "source": "OpenAlex", "query_id": "Q1", "title": f"Unrelated paper {j}",
                        "authors": "Other, Olga", "year": str(year), "doi": f"10.5555/noise.{j}"})
        screening.append({"record_id": rid, "stage": "ta", "decision": "exclude", "reason_code": code})
    records.append({"record_id": "OLD1", "source": "Crossref", "query_id": "Q2", "title": "An old classic",
                    "authors": "Classic, Carl", "year": str(y0 - 6), "doi": "10.5555/old.1"})
    w = lambda key, rows: write_csv(folder / FILES[key], rows, HEADERS[FILES[key]])  # noqa: E731
    w("records", records)
    w("search_log", log)
    w("screening", screening)
    w("verification", ver)
    w("extraction", ext)
    w("cards", cards)
    w("weaknesses", weak)
    w("fulltext", ft)
    return ref_ids
