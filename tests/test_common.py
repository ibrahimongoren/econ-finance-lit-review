from litrev_common import (find_record, first_author_family, is_other_method, norm_doi,
                           surname_match, title_similarity, to_int)


def test_norm_doi_strips_resolver_and_case():
    assert norm_doi("https://doi.org/10.1257/AER.20181169") == "10.1257/aer.20181169"
    assert norm_doi("doi: 10.1111/joes.12363.") == "10.1111/joes.12363"
    assert norm_doi("") == ""


def test_surname_match_handles_diacritics_particles_and_compounds():
    assert surname_match("Iršová", "Irsova")
    assert surname_match("Öngören", "Ongoren")
    assert surname_match("de Chaisemartin", "Chaisemartin")
    assert surname_match("Geyer-Klingeberg", "Klingeberg")
    assert not surname_match("Smith", "Smyth")


def test_title_similarity_tolerates_case_and_subtitles():
    a = "Two-Way Fixed Effects Estimators with Heterogeneous Treatment Effects"
    assert title_similarity(a, a.lower() + ".") > 0.98
    assert title_similarity("Monetary policy: evidence from Turkey", "Monetary policy") > 0.95
    assert title_similarity(a, "Difference-in-differences with multiple time periods") < 0.6


def test_find_record_by_doi_then_title():
    rows = [{"record_id": "R1", "title": "A paper on banks", "authors": "Kaya, Ali", "year": "2020", "doi": "10.1/x"},
            {"record_id": "R2", "title": "Inflation and the exchange rate", "authors": "Demir, Ayşe", "year": "2019"}]
    assert find_record(rows, doi="https://doi.org/10.1/X")["record_id"] == "R1"
    assert find_record(rows, title="Inflation and the Exchange Rate", authors="Demir, A.")["record_id"] == "R2"
    assert find_record(rows, title="Inflation and the Exchange Rate", authors="Yilmaz, B.") is None


def test_small_helpers():
    assert first_author_family("Andrews, Isaiah; Kasy, Maximilian") == "Andrews"
    assert to_int("published 2023-11-23") == 2023
    assert is_other_method("snowball-backward") and is_other_method("prior-review")
    assert not is_other_method("Crossref")
