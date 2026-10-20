"""Init, de-duplication, coverage, screening consistency, PRISMA and workbook export."""

import json

import pytest

from conftest import rec, run, write
from dedupe_records import dedupe
from litrev_common import FILES, read_csv
from screening_check import cohen_kappa

AER = "Two-Way Fixed Effects Estimators with Heterogeneous Treatment Effects"
AUTH = "de Chaisemartin, Clément; D'Haultfœuille, Xavier"


def test_init_creates_every_file_and_is_idempotent(folder, tmp_path):
    for name in FILES.values():
        if name.endswith((".csv", ".md")) and name not in (FILES["records_dedup"], FILES["duplicates"],
                                                            FILES["rescreen"]):
            assert (folder / name).exists(), name
    assert (folder / FILES["meta_dir"]).is_dir()
    assert read_csv(folder / FILES["records"]) == []
    (folder / FILES["protocol"]).write_text("edited", encoding="utf-8")
    code, out = run("init_review.py", "Test review", "--dir", tmp_path)
    assert code == 0 and "Kept existing" in out
    assert (folder / FILES["protocol"]).read_text(encoding="utf-8") == "edited"


def test_init_turkish_template(tmp_path):
    code, _ = run("init_review.py", "İklim riski", "--lang", "tr", "--dir", tmp_path)
    assert code == 0
    text = (tmp_path / "litrev-iklim-riski" / FILES["protocol"]).read_text(encoding="utf-8")
    assert "Araştırma soruları" in text and "Durdurma kuralı" in text


def test_dedupe_doi_fuzzy_and_wp_pairs():
    rows = [
        rec("R1", AER, AUTH, 2020, doi="10.1257/aer.20181169"),
        rec("R2", AER.lower(), "Chaisemartin, C.; D'Haultfoeuille, X.", 2018, doi="10.3386/w25904",
            type_="working-paper"),
        rec("R3", AER + ".", AUTH, 2020, doi="https://doi.org/10.1257/AER.20181169"),
        rec("R4", "Difference-in-Differences with multiple time periods", "Callaway, Brantly", 2021),
        rec("R5", "Difference-in-differences with multiple time periods", "Callaway, B.", 2021),
        rec("R6", "Fiscal rules and debt", "Doe, Jane", 2019),
    ]
    unique, dups = dedupe(rows)
    rel = {(d["record_id"], d["relation"]) for d in dups}
    assert ("R3", "duplicate") in rel           # same DOI
    assert ("R5", "duplicate") in rel           # same title, author, year
    assert ("R2", "same-study") in rel          # working paper of R1
    assert {r["record_id"] for r in unique} == {"R1", "R2", "R4", "R6"}


def test_dedupe_cli_merges_worker_files_and_rejects_clashing_ids(folder):
    write(folder, "records", [rec("R1", AER, AUTH, 2020)])
    part = folder / "03_records_part-A.csv"
    part.write_text((folder / FILES["records"]).read_text(encoding="utf-8").replace("R1,", "A-001,"),
                    encoding="utf-8")
    code, out = run("dedupe_records.py", folder)
    assert code == 0, out
    assert "03_records_part-A.csv (+1)" in out
    assert len(read_csv(folder / FILES["records"])) == 2
    assert len(read_csv(folder / FILES["records_dedup"])) == 1


def _coverage_fixture(folder, extra_new_in_tail=False):
    write(folder, "seeds", [{"seed_id": "S1", "title": AER, "authors": AUTH, "year": "2020"},
                            {"seed_id": "S2", "title": "Fiscal rules and debt", "authors": "Doe, Jane",
                             "year": "2019"}])
    log = [{"query_id": q, "source": "Crossref"} for q in ("Q1", "Q2", "Q3", "Q4", "Q5")]
    write(folder, "search_log", log)
    recs = [rec(f"R{i}", f"Distinct paper number {i} about money", f"Author{i}, A.", 2020, query="Q1")
            for i in range(1, 21)]
    recs += [rec("R21", AER, AUTH, 2020, query="Q2"), rec("R22", "Fiscal rules and debt", "Doe, Jane", 2019,
                                                       query="Q2")]
    recs += [rec("R23", AER, AUTH, 2020, query="Q3"), rec("R24", "Fiscal rules and debt", "Doe, Jane", 2019,
                                                       query="Q4")]
    recs += [rec("R25", "A genuinely new study", "New, N.", 2024, query="Q5")] if extra_new_in_tail else []
    write(folder, "records", recs)
    (folder / FILES["duplicates"]).write_text(
        "record_id,duplicate_of,relation,basis,similarity\nR23,R21,duplicate,doi,1.00\nR24,R22,duplicate,t,1.00\n",
        encoding="utf-8")


def test_coverage_pass_when_seeds_found_and_saturated(folder):
    _coverage_fixture(folder)
    code, out = run("coverage_check.py", folder)
    assert "Seed recall: 2/2" in out
    assert "Saturation: PASS" in out and code == 0
    assert (folder / "03_coverage.md").exists()


def test_coverage_fails_on_missing_seed_and_late_novelty(folder):
    _coverage_fixture(folder, extra_new_in_tail=True)
    rows = read_csv(folder / FILES["seeds"]) + [{"seed_id": "S3", "title": "A missing classic", "authors": "Old, O.",
                                                 "year": "1990"}]
    write(folder, "seeds", rows)
    write(folder, "screening", [{"record_id": "R21", "stage": "ta", "decision": "include"},
                                {"record_id": "R25", "stage": "ta", "decision": "include"}])
    code, out = run("coverage_check.py", folder)
    assert code == 1
    assert "Seed recall: 2/3" in out and "**NO**" in out
    assert "Saturation: NOT YET" in out


def test_cohen_kappa_textbook_case():
    pairs = [("in", "in")] * 20 + [("in", "out")] * 5 + [("out", "in")] * 10 + [("out", "out")] * 15
    po, k = cohen_kappa(pairs)
    assert po == pytest.approx(0.7)
    assert k == pytest.approx(0.4)


def test_screening_sample_is_blind_and_compare_reports_kappa(folder):
    recs = [rec(f"R{i}", f"Title {i}", f"A{i}, B.", 2020) for i in range(30)]
    write(folder, "records", recs)
    write(folder, "screening", [{"record_id": f"R{i}", "stage": "ta",
                                 "decision": "include" if i < 6 else "exclude"} for i in range(30)])
    code, out = run("screening_check.py", "sample", folder, "--n", "12", "--seed", "3")
    assert code == 0, out
    sample = read_csv(folder / FILES["rescreen"])
    assert len(sample) == 12 and all(r["decision"] == "" for r in sample)
    first = {r["record_id"]: r["decision"] for r in read_csv(folder / FILES["screening"])}
    for r in sample:                                 # agree everywhere -> kappa 1
        r["decision"] = first[r["record_id"]]
    from litrev_common import write_csv
    write_csv(folder / FILES["rescreen"], sample, list(sample[0].keys()))
    code, out = run("screening_check.py", "compare", folder)
    assert code == 0 and "kappa: 1.00" in out
    sample[0]["decision"] = "exclude" if sample[0]["decision"] != "exclude" else "include"
    sample[1]["decision"] = "exclude" if sample[1]["decision"] != "exclude" else "include"
    sample[2]["decision"] = "exclude" if sample[2]["decision"] != "exclude" else "include"
    write_csv(folder / FILES["rescreen"], sample, list(sample[0].keys()))
    code, out = run("screening_check.py", "compare", folder, "--min-kappa", "0.95")
    assert code == 1 and "Disagreements" in out


def test_prisma_counts(folder):
    recs = [rec("R1", AER, AUTH, 2020), rec("R2", AER, AUTH, 2018, type_="working-paper", source="WebSearch:nber.org"),
            rec("R3", AER, AUTH, 2020, source="Consensus"), rec("R4", "Other A", "X, Y.", 2021),
            rec("R5", "Other B", "Z, W.", 2021, source="snowball-backward"),
            rec("R6", "Other C", "Q, R.", 2022, source="author")]
    write(folder, "records", recs)
    (folder / FILES["duplicates"]).write_text(
        "record_id,duplicate_of,relation,basis,similarity\nR3,R1,duplicate,doi,1.00\nR2,R1,same-study,t,1.00\n",
        encoding="utf-8")
    write(folder, "screening", [
        {"record_id": "R1", "stage": "ta", "decision": "include"},
        {"record_id": "R2", "stage": "ta", "decision": "include"},
        {"record_id": "R4", "stage": "ta", "decision": "exclude", "reason_code": "E1"},
        {"record_id": "R5", "stage": "ta", "decision": "maybe"},
        {"record_id": "R6", "stage": "ta", "decision": "include"},
        {"record_id": "R1", "stage": "ft", "decision": "include"},
        {"record_id": "R2", "stage": "ft", "decision": "include"},
        {"record_id": "R5", "stage": "ft", "decision": "exclude", "reason_code": "E3"},
        {"record_id": "R6", "stage": "ft", "decision": "not_retrieved"},
    ])
    code, out = run("prisma_flow.py", folder, "--no-figure")
    assert code == 0, out
    c = json.loads((folder / FILES["prisma_counts"]).read_text(encoding="utf-8"))
    assert c["identified_total"] == 6 and c["identified_other_methods"] == 2
    assert c["duplicates_removed"] == 1 and c["records_screened"] == 5
    assert c["records_excluded_title_abstract"] == 1
    assert c["reports_sought"] == 4 and c["reports_not_retrieved"] == 1
    assert c["reports_assessed"] == 3 and c["reports_excluded_full_text"] == 1
    assert c["exclusion_reasons"] == {"E3": 1}
    assert c["reports_included"] == 2 and c["studies_included"] == 1


def test_prisma_figure_written(folder):
    pytest.importorskip("matplotlib")
    write(folder, "records", [rec("R1", AER, AUTH, 2020)])
    write(folder, "screening", [{"record_id": "R1", "stage": "ta", "decision": "include"}])
    code, out = run("prisma_flow.py", folder, "--lang", "tr")
    assert code == 0, out
    assert (folder / "04_prisma_flow.png").stat().st_size > 10_000


def test_export_workbook(folder):
    openpyxl = pytest.importorskip("openpyxl")
    write(folder, "records", [rec("R1", AER, AUTH, 2020)])
    write(folder, "screening", [{"record_id": "R1", "stage": "ta", "decision": "include"}])
    run("prisma_flow.py", folder, "--no-figure")
    code, out = run("export_workbook.py", folder)
    assert code == 0, out
    wb = openpyxl.load_workbook(folder / "evidence_workbook.xlsx")
    assert {"README", "Records", "Screening", "PRISMA counts"} <= set(wb.sheetnames)
