#!/usr/bin/env python3
"""Per-study reading cards: three passes, "what did it do / what did it leave out", weaknesses.

Usage:
    python3 scripts/study_cards.py init  litrev-<slug>/ [--window 2021-2026]
    python3 scripts/study_cards.py check litrev-<slug>/
    python3 scripts/study_cards.py chat  litrev-<slug>/ [--lang tr|en] [--batch 8] [--part 1] [--order theme|year]
    python3 scripts/study_cards.py md    litrev-<slug>/ [--lang tr|en] [--out cards.md]
    python3 scripts/study_cards.py stats litrev-<slug>/ [--lang tr|en]

Files
  06_study_cards.csv  one row per included study in the publication window:
      ref_id, theme, pass1_abstract_conclusion, pass2_intro_method, pass3_literature,
      what_it_did, what_it_left_out, relevance, full_text_source, evidence_level ([FT] or [AB]),
      card_status (todo / draft / checked), notes
  06_weaknesses.csv   one row per weakness:
      ref_id, category (see below), severity (high / medium / low), weakness,
      evidence_location (section, page, table or 'abstract'), basis (author-stated / reviewer-identified), notes
  Categories: question_contribution, theory_specification, identification, data_measurement,
  estimation_inference, robustness, external_validity, literature_positioning,
  transparency_replication, policy_interpretation

init   creates a 'todo' card for every printable study in 05_verification.csv whose year is inside the
       window (window from --window, else 00_protocol.md, else the last five years); older studies are
       listed as background, not carded. Existing cards are never overwritten.
check  fails (exit 1) when a card is incomplete or a weakness is not grounded - see references/study-cards.md.
chat   renders cards as chat-ready Markdown in batches, with the verified link of every study.
md     renders all cards for the report. stats summarizes weaknesses by category and severity.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import (FILES, HEADERS, PRINTABLE_STATUSES, SEVERITIES, WEAKNESS_BASES,  # noqa: E402
                           WEAKNESS_CATEGORIES, WEAKNESS_LABELS, family_name, in_window, norm_doi, parse_window,
                           read_csv, split_authors, to_int, window_from_protocol, write_csv)

L = {
    "tr": {"p1": "1. tur — Özet → Sonuç", "p2": "2. tur — Giriş → Yöntem", "p3": "3. tur — Literatür taraması",
           "did": "NE YAPMIŞ?", "left": "NEYİ EKSİK BIRAKMIŞ?", "weak": "Zayıf yönler",
           "rel": "Çalışmana katkısı", "ft": "Tam metin", "and": "ve", "etal": "vd.",
           "part": "Bölüm", "of": "/", "sev": {"high": "yüksek", "medium": "orta", "low": "düşük"},
           "basis": {"author-stated": "yazarlarca belirtilmiş", "reviewer-identified": "inceleyen tespiti"},
           "na": "—", "theme": "Tema", "heading": "Çalışma kartları",
           "ab_note": "Yalnızca özet okunabildi; 2. ve 3. tur yapılamadı.",
           "na_weak": "özetten değerlendirilemedi; tam metin gerekli.",
           "status": {"VERIFIED": "✅ doğrulandı", "PARTIAL": "🟡 kısmen doğrulandı", "PREPRINT": "📄 çalışma tebliği"},
           "plain": {"VERIFIED": "doğrulandı", "PARTIAL": "kısmen doğrulandı", "PREPRINT": "çalışma tebliği / ön baskı"},
           "tbl": ("Kategori", "Zayıf yön", "Çalışma")},
    "en": {"p1": "Pass 1 — Abstract → Conclusion", "p2": "Pass 2 — Introduction → Methodology",
           "p3": "Pass 3 — Literature review", "did": "WHAT DID IT DO?", "left": "WHAT DID IT LEAVE OUT?",
           "weak": "Weaknesses", "rel": "Relevance to your study", "ft": "Full text", "and": "&", "etal": "et al.",
           "part": "Part", "of": "of", "sev": {"high": "high", "medium": "medium", "low": "low"},
           "basis": {"author-stated": "author-stated", "reviewer-identified": "reviewer-identified"},
           "na": "—", "theme": "Theme", "heading": "Study cards",
           "ab_note": "Abstract only; passes 2 and 3 were not possible.",
           "na_weak": "not assessable from the abstract; full text needed.",
           "status": {"VERIFIED": "✅ verified", "PARTIAL": "🟡 partially verified", "PREPRINT": "📄 working paper"},
           "plain": {"VERIFIED": "verified", "PARTIAL": "partially verified", "PREPRINT": "working paper / preprint"},
           "tbl": ("Category", "Weaknesses", "Studies")},
}


def load(folder: Path) -> tuple[list[dict], dict, dict, dict]:
    cards_path, weak_path = folder / FILES["cards"], folder / FILES["weaknesses"]
    cards = read_csv(cards_path) if cards_path.exists() else []
    weak = defaultdict(list)
    for w in (read_csv(weak_path) if weak_path.exists() else []):
        weak[w.get("ref_id", "")].append(w)
    ver = {r["ref_id"]: r for r in read_csv(folder / FILES["verification"])} \
        if (folder / FILES["verification"]).exists() else {}
    ext_path = folder / FILES["extraction"]
    ext = {r["ref_id"]: r for r in read_csv(ext_path)} if ext_path.exists() else {}
    return cards, weak, ver, ext


def short_cite(v: dict, lang: str) -> str:
    fams = [family_name(a) for a in split_authors(v.get("authors", ""))]
    year = v.get("year") or "n.d."
    if not fams:
        return f"{(v.get('title') or '')[:40]} ({year})"
    if len(fams) == 1:
        who = fams[0]
    elif len(fams) == 2:
        who = f"{fams[0]} {L[lang]['and']} {fams[1]}"
    else:
        who = f"{fams[0]} {L[lang]['etal']}"
    return f"{who} ({year})"


def link_of(v: dict) -> str:
    d = norm_doi(v.get("doi", ""))
    return f"https://doi.org/{d}" if d else (v.get("link") or "").strip()


def window_for(folder: Path, arg: str) -> tuple[int, int]:
    return parse_window(arg) if arg else (window_from_protocol(folder) or parse_window(""))


# ---------------------------------------------------------------------------
def cmd_init(folder: Path, window_arg: str) -> int:
    window = window_for(folder, window_arg)
    cards, _, ver, ext = load(folder)
    have = {c["ref_id"] for c in cards}
    ft_path = folder / FILES["fulltext"]
    ft = {r["ref_id"]: r for r in read_csv(ft_path)} if ft_path.exists() else {}
    added, background = [], []
    for ref_id, v in ver.items():
        if (v.get("status") or "").upper() not in PRINTABLE_STATUSES:
            continue
        inside = in_window(v.get("year"), window)
        if inside is False:
            background.append(ref_id)
            continue
        if ref_id in have:
            continue
        added.append({"ref_id": ref_id, "theme": (ext.get(ref_id) or {}).get("theme", ""),
                      "full_text_source": (ft.get(ref_id) or {}).get("oa_url", ""), "card_status": "todo"})
    write_csv(folder / FILES["cards"], cards + added, HEADERS[FILES["cards"]])
    if not (folder / FILES["weaknesses"]).exists():
        write_csv(folder / FILES["weaknesses"], [], HEADERS[FILES["weaknesses"]])
    print(f"Window {window[0]}-{window[1]}: {len(added)} new card(s), {len(cards)} kept, "
          f"{len(background)} background reference(s) outside the window (not carded).")
    if background:
        print("Background: " + ", ".join(sorted(background)))
    return 0


NOT_ASSESSABLE = re.compile(r"not assessable|de[gğ]erlendirilemedi", re.I)


def weakness_waived(c: dict) -> bool:
    """Abstract-only cards may skip weaknesses when the notes say they could not be assessed."""
    level = (c.get("evidence_level") or "").strip().upper().strip("[]")
    return level == "AB" and bool(NOT_ASSESSABLE.search(c.get("notes") or ""))


def card_problems(c: dict, weaknesses: list[dict], window, v: dict | None) -> list[str]:
    p = []
    level = (c.get("evidence_level") or "").strip().upper().strip("[]")
    for field in ("pass1_abstract_conclusion", "what_it_did", "what_it_left_out", "relevance"):
        if not (c.get(field) or "").strip():
            p.append(f"{field} empty")
    if level not in ("FT", "AB"):
        p.append("evidence_level must be [FT] or [AB]")
    if level == "FT":
        for field in ("pass2_intro_method", "pass3_literature"):
            if not (c.get(field) or "").strip():
                p.append(f"{field} empty (required for a full-text card)")
        if not (c.get("full_text_source") or "").strip():
            p.append("full_text_source empty (say where the full text was read)")
    if not weaknesses and not weakness_waived(c):
        p.append("no weakness recorded (every study gets at least one, grounded; abstract-only cards may "
                 "instead say 'weaknesses not assessable from the abstract' in notes)")
    for w in weaknesses:
        tag = f"weakness '{(w.get('weakness') or '')[:30]}'"
        if (w.get("category") or "") not in WEAKNESS_CATEGORIES:
            p.append(f"{tag}: unknown category '{w.get('category')}'")
        if (w.get("severity") or "").lower() not in SEVERITIES:
            p.append(f"{tag}: severity must be high/medium/low")
        if (w.get("basis") or "").lower() not in WEAKNESS_BASES:
            p.append(f"{tag}: basis must be author-stated or reviewer-identified")
        if not (w.get("weakness") or "").strip():
            p.append("weakness text empty")
        if not (w.get("evidence_location") or "").strip():
            p.append(f"{tag}: evidence_location empty (section/page/table, or 'abstract')")
    if v is None:
        p.append("ref_id not in 05_verification.csv")
    elif (v.get("status") or "").upper() not in PRINTABLE_STATUSES:
        p.append(f"source status {v.get('status')} - cannot be carded as evidence")
    elif window and in_window(v.get("year"), window) is False:
        p.append("year outside the review window - move to background")
    return p


def cmd_check(folder: Path, window_arg: str) -> int:
    window = window_for(folder, window_arg)
    cards, weak, ver, _ = load(folder)
    carded = {c["ref_id"] for c in cards}
    missing = [r for r, v in ver.items() if (v.get("status") or "").upper() in PRINTABLE_STATUSES
               and in_window(v.get("year"), window) is not False and r not in carded]
    issues, complete, ab = {}, 0, 0
    for c in cards:
        probs = card_problems(c, weak.get(c["ref_id"], []), window, ver.get(c["ref_id"]))
        if probs:
            issues[c["ref_id"]] = probs
        else:
            complete += 1
        if (c.get("evidence_level") or "").upper().strip("[]") == "AB":
            ab += 1
    orphan = sorted(set(weak) - carded)
    print(f"Window {window[0]}-{window[1]} · cards: {len(cards)} · complete: {complete} · "
          f"incomplete: {len(issues)} · abstract-only: {ab}")
    if missing:
        print("Included studies without a card: " + ", ".join(sorted(missing)))
    if orphan:
        print("Weaknesses for unknown cards: " + ", ".join(orphan))
    for ref, probs in sorted(issues.items()):
        print(f"  {ref}: " + "; ".join(probs))
    ok = not issues and not missing and not orphan
    print("RESULT: " + ("PASS" if ok else "FAIL - complete the cards before delivery"))
    return 0 if ok else 1


def ordered(cards: list[dict], ver: dict, order: str) -> list[dict]:
    def key(c):
        v = ver.get(c["ref_id"], {})
        year = to_int(v.get("year")) or 0
        if order == "year":
            return (-year, short_cite(v, "en"))
        return ((c.get("theme") or "~").lower(), -year, short_cite(v, "en"))
    return sorted(cards, key=key)


def render_card(n: int, c: dict, weaknesses: list[dict], v: dict, lang: str, report: bool = False) -> str:
    """Markdown for one card. report=True: a level-3 heading and plain status words (no emoji) for DOCX/PDF."""
    t = L[lang]
    level = (c.get("evidence_level") or "").upper().strip("[]")
    status = t["plain" if report else "status"].get((v.get("status") or "").upper(), v.get("status", ""))
    if report:
        head = f"### [{n}] {short_cite(v, lang)} — *{(v.get('title') or '').strip()}*"
    else:
        head = f"**[{n}] {short_cite(v, lang)}** — *{(v.get('title') or '').strip()}*"
    meta = " · ".join(x for x in (v.get("venue"), link_of(v), status, f"[{level}]" if level else "") if x)
    lines = [head, "", meta, ""]
    lines.append(f"- **{t['p1']}:** {c.get('pass1_abstract_conclusion') or t['na']}")
    if level == "AB":
        lines.append(f"- *{t['ab_note']}*")
    else:
        lines.append(f"- **{t['p2']}:** {c.get('pass2_intro_method') or t['na']}")
        lines.append(f"- **{t['p3']}:** {c.get('pass3_literature') or t['na']}")
    lines.append(f"- **{t['did']}** {c.get('what_it_did') or t['na']}")
    lines.append(f"- **{t['left']}** {c.get('what_it_left_out') or t['na']}")
    if not weaknesses and weakness_waived(c):
        lines.append(f"- **{t['weak']}:** {t['na_weak']}")
    if weaknesses:
        lines.append(f"- **{t['weak']}:**")
        sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
        for w in sorted(weaknesses, key=lambda w: sev_rank.get((w.get("severity") or "").lower(), 9)):
            cat = WEAKNESS_LABELS[lang].get(w.get("category", ""), w.get("category", ""))
            sev = t["sev"].get((w.get("severity") or "").lower(), w.get("severity", ""))
            basis = t["basis"].get((w.get("basis") or "").lower(), w.get("basis", ""))
            loc = w.get("evidence_location", "")
            lines.append(f"  - [{cat} · {sev}] {w.get('weakness', '').strip()} "
                         f"({basis}{'; ' + loc if loc else ''})")
    if c.get("relevance"):
        lines.append(f"- **{t['rel']}:** {c['relevance']}")
    if c.get("full_text_source"):
        lines.append(f"- {t['ft']}: {c['full_text_source']}")
    return "\n".join(lines)


def cmd_render(folder: Path, lang: str, batch: int, part: int, order: str, out: str, chat: bool) -> int:
    cards, weak, ver, _ = load(folder)
    cards = [c for c in ordered(cards, ver, order) if c["ref_id"] in ver]
    if not cards:
        print("No cards yet - run: study_cards.py init")
        return 1
    numbered = list(enumerate(cards, 1))
    blocks = []
    if chat:
        parts = [numbered[i:i + batch] for i in range(0, len(numbered), batch)]
        part = max(1, min(part, len(parts)))
        chunk = parts[part - 1]
        blocks.append(f"### {L[lang]['heading']} — {L[lang]['part']} {part} {L[lang]['of']} {len(parts)} "
                      f"({chunk[0][0]}–{chunk[-1][0]} / {len(cards)})")
        selection = chunk
    else:
        blocks.append(f"## {L[lang]['heading']}")
        selection = numbered
    theme = None
    for n, c in selection:
        if order != "year" and (c.get("theme") or "") != theme:
            theme = c.get("theme") or ""
            if theme:
                blocks.append(f"#### {L[lang]['theme']}: {theme}")
        blocks.append(render_card(n, c, weak.get(c["ref_id"], []), ver[c["ref_id"]], lang))
    text = "\n\n".join(blocks) + "\n"
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(text)
    return 0


def cmd_stats(folder: Path, lang: str) -> int:
    cards, weak, ver, _ = load(folder)
    all_w = [w for ws in weak.values() for w in ws]
    by_cat = Counter(w.get("category") for w in all_w)
    studies_by_cat = Counter(cat for ref, ws in weak.items() for cat in {w.get("category") for w in ws})
    sev = Counter((w.get("severity") or "").lower() for w in all_w)
    levels = Counter((c.get("evidence_level") or "").upper().strip("[]") or "?" for c in cards)
    themes = Counter(c.get("theme") or "(no theme)" for c in cards)
    print(f"Cards: {len(cards)} · full text: {levels.get('FT', 0)} · abstract only: {levels.get('AB', 0)}")
    print("Themes: " + ", ".join(f"{k} {v}" for k, v in themes.most_common()))
    print(f"Weaknesses: {len(all_w)} (high {sev.get('high', 0)}, medium {sev.get('medium', 0)}, "
          f"low {sev.get('low', 0)})")
    h = L[lang]["tbl"]
    print(f"\n| {h[0]} | {h[1]} | {h[2]} |\n|---|---|---|")
    for cat in WEAKNESS_CATEGORIES:
        if by_cat.get(cat):
            print(f"| {WEAKNESS_LABELS[lang][cat]} | {by_cat[cat]} | {studies_by_cat[cat]} |")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "check", "chat", "md", "stats"):
        s = sub.add_parser(name)
        s.add_argument("folder")
        s.add_argument("--window", default="")
        s.add_argument("--lang", choices=["tr", "en"], default="en")
        s.add_argument("--batch", type=int, default=8)
        s.add_argument("--part", type=int, default=1)
        s.add_argument("--order", choices=["theme", "year"], default="theme")
        s.add_argument("--out", default="")
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    if not (folder / FILES["verification"]).exists():
        print(f"{FILES['verification']} not found in {folder}")
        return 1
    if a.cmd == "init":
        return cmd_init(folder, a.window)
    if a.cmd == "check":
        return cmd_check(folder, a.window)
    if a.cmd == "stats":
        return cmd_stats(folder, a.lang)
    return cmd_render(folder, a.lang, a.batch, a.part, a.order, a.out, chat=(a.cmd == "chat"))


if __name__ == "__main__":
    sys.exit(main())
