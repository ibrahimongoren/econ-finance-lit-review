"""Publication window, E7 screening, study cards (three passes, weaknesses) and chat rendering."""

import datetime as dt
import json

import pytest

from conftest import rec, run, write
from litrev_common import (FILES, default_window, in_window, parse_window, read_csv, window_from_protocol,
                           write_csv, HEADERS)
import study_cards


def test_parse_window_forms():
    today = dt.date(2026, 10, 20)
    assert default_window(today) == (2021, 2026)
    assert parse_window("", today) == (2021, 2026)
    assert parse_window("2020-2026", today) == (2020, 2026)
    assert parse_window("2020 – günümüz", today) == (2020, 2026)
    assert parse_window("2019-present", today) == (2019, 2026)
    assert parse_window("2022", today) == (2022, 2022)
    assert parse_window("son 10 yıl", today) == (2016, 2026)
    assert parse_window("last 3 years", today) == (2023, 2026)
    assert parse_window("2019'dan beri", today) == (2019, 2026)
    assert parse_window("since 2018", today) == (2018, 2026)
    with pytest.raises(ValueError):
        parse_window("since 2031", today)
    with pytest.raises(ValueError):
        parse_window("2026-2020", today)
    with pytest.raises(ValueError):
        parse_window("last decade", today)
    assert in_window("2021", (2021, 2026)) is True
    assert in_window("published 2019-05", (2021, 2026)) is False
    assert in_window("", (2021, 2026)) is None


def test_init_writes_default_and_user_window(tmp_path):
    code, out = run("init_review.py", "Default window", "--dir", tmp_path)
    assert code == 0 and "default" in out
    y = dt.date.today().year
    assert window_from_protocol(tmp_path / "litrev-default-window") == (y - 5, y)
    code, out = run("init_review.py", "Pencere", "--lang", "tr", "--window", "2020-günümüz", "--dir", tmp_path)
    assert code == 0
    folder = tmp_path / "litrev-pencere"
    text = (folder / FILES["protocol"]).read_text(encoding="utf-8")
    assert "Literatür penceresi: 2020-" in text and "E7:" in text and "araştırma sorusu" in text
    assert window_from_protocol(folder) == (2020, y)
    report = (folder / FILES["report_md"]).read_text(encoding="utf-8")
    assert "{{CARDS}}" in report and "{{FIGURE:prisma}}" in report and "# Kısa cevap" in report
    assert (folder / FILES["figures_dir"]).is_dir()
    code, _ = run("init_review.py", "Bad", "--window", "soon", "--dir", tmp_path)
    assert code == 2


def test_screening_window_marks_e7_once_and_prisma_reports_it(demo):
    code, out = run("dedupe_records.py", demo)
    assert code == 0, out
    code, out = run("screening_check.py", "window", demo)
    assert code == 0 and "outside (new E7): 1" in out
    e7 = [r for r in read_csv(demo / FILES["screening"]) if r["reason_code"] == "E7"]
    assert [r["record_id"] for r in e7] == ["OLD1"]
    code, out = run("screening_check.py", "window", demo)          # idempotent
    assert "outside (new E7): 0" in out
    run("prisma_flow.py", demo, "--no-figure")
    c = json.loads((demo / FILES["prisma_counts"]).read_text(encoding="utf-8"))
    assert c["removed_outside_window"] == 1
    assert c["records_screened"] == 14 and c["records_excluded_title_abstract"] == 2
    assert c["studies_included"] == 12


def test_screening_window_dry_run_and_unknown_year(folder):
    write(folder, "records", [rec("R1", "Paper one", "Doe, Jane", 2010), rec("R2", "Paper two", "Doe, Jane", "")])
    (folder / FILES["protocol"]).write_text("Literature window: 2021-2026\n", encoding="utf-8")
    code, out = run("screening_check.py", "window", folder, "--dry-run")
    assert code == 0 and "year unknown: 1" in out and "Dry run" in out
    assert read_csv(folder / FILES["screening"]) == []


def test_cards_check_passes_on_complete_demo(demo):
    code, out = run("study_cards.py", "check", demo)
    assert code == 0, out
    assert "complete: 12" in out and "abstract-only: 3" in out


def test_cards_check_catches_incomplete_and_ungrounded(demo):
    cards = read_csv(demo / FILES["cards"])
    cards[1]["what_it_left_out"] = ""
    cards[2]["pass2_intro_method"] = ""                      # S03 is a full-text card
    write_csv(demo / FILES["cards"], cards, HEADERS[FILES["cards"]])
    weak = read_csv(demo / FILES["weaknesses"])
    weak[0]["evidence_location"] = ""
    weak[1]["category"] = "vibes"
    write_csv(demo / FILES["weaknesses"], weak, HEADERS[FILES["weaknesses"]])
    code, out = run("study_cards.py", "check", demo)
    assert code == 1 and "RESULT: FAIL" in out
    assert "what_it_left_out empty" in out and "pass2_intro_method empty" in out
    assert "evidence_location empty" in out and "unknown category 'vibes'" in out


def test_abstract_card_may_waive_weaknesses_only_with_a_note(demo):
    weak = [w for w in read_csv(demo / FILES["weaknesses"]) if w["ref_id"] != "S01"]   # S01 is [AB]
    write_csv(demo / FILES["weaknesses"], weak, HEADERS[FILES["weaknesses"]])
    code, out = run("study_cards.py", "check", demo)
    assert code == 1 and "no weakness recorded" in out
    cards = read_csv(demo / FILES["cards"])
    cards[0]["notes"] = "zayıf yönler özetten değerlendirilemedi"
    write_csv(demo / FILES["cards"], cards, HEADERS[FILES["cards"]])
    code, out = run("study_cards.py", "check", demo)
    assert code == 0, out
    code, out = run("study_cards.py", "chat", demo, "--lang", "tr", "--batch", "12")
    assert "özetten değerlendirilemedi" in out


def test_cards_init_cards_window_only_and_keeps_existing(folder):
    (folder / FILES["protocol"]).write_text("Literature window: 2021-2026\n", encoding="utf-8")
    ver = [{"ref_id": "New2023", "status": "VERIFIED", "year": "2023", "title": "A", "authors": "Doe, Jane"},
           {"ref_id": "Old2015", "status": "VERIFIED", "year": "2015", "title": "B", "authors": "Roe, Rick"},
           {"ref_id": "Bad2022", "status": "NOT_VERIFIED", "year": "2022", "title": "C", "authors": "Poe, Ed"}]
    write(folder, "verification", ver)
    code, out = run("study_cards.py", "init", folder)
    assert code == 0 and "1 new card" in out and "Old2015" in out
    cards = read_csv(folder / FILES["cards"])
    assert [c["ref_id"] for c in cards] == ["New2023"] and cards[0]["card_status"] == "todo"
    cards[0]["what_it_did"] = "kept"
    write_csv(folder / FILES["cards"], cards, HEADERS[FILES["cards"]])
    run("study_cards.py", "init", folder)
    assert read_csv(folder / FILES["cards"])[0]["what_it_did"] == "kept"


def test_chat_render_turkish_labels_links_and_batches(demo):
    code, out = run("study_cards.py", "chat", demo, "--lang", "tr", "--batch", "5", "--part", "3")
    assert code == 0
    assert "Bölüm 3 / 3 (11–12 / 12)" in out
    assert "NE YAPMIŞ?" in out and "NEYİ EKSİK BIRAKMIŞ?" in out and "1. tur — Özet → Sonuç" in out
    assert "https://doi.org/10.5555/demo." in out and "Zayıf yönler" in out
    code, out = run("study_cards.py", "chat", demo, "--lang", "en", "--batch", "50")
    assert "WHAT DID IT LEAVE OUT?" in out and "Pass 3 — Literature review" in out
    assert out.count("**[") == 12


def test_render_card_report_mode_has_heading_and_no_emoji(demo):
    cards, weak, ver, _ = study_cards.load(demo)
    card = cards[2]
    md = study_cards.render_card(3, card, weak[card["ref_id"]], ver[card["ref_id"]], "tr", report=True)
    assert md.startswith("### [3] ") and "✅" not in md and "doğrulandı" in md
    chat = study_cards.render_card(3, card, weak[card["ref_id"]], ver[card["ref_id"]], "tr")
    assert chat.startswith("**[3] ") and "✅" in chat


def test_stats_counts_weaknesses(demo):
    code, out = run("study_cards.py", "stats", demo, "--lang", "tr")
    assert code == 0 and "Weaknesses: 24 (high 8, medium 8, low 8)" in out
    assert "| Kategori | Zayıf yön | Çalışma |" in out
