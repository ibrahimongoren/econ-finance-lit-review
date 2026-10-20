#!/usr/bin/env python3
"""Create the working folder for a staged literature review.

Usage:
    python3 scripts/init_review.py "Climate risk and monetary transmission" --mode comprehensive --lang en
    python3 scripts/init_review.py "..." --lang tr --window 2020-2026 --dir /path/to/parent
    python3 scripts/init_review.py "..." --window 2019-present

Creates litrev-<slug>/ with the protocol template (English or Turkish; other languages get the English
template to translate), every CSV with its fixed header, the 10_figures/ folder and a 10_report.md
skeleton with figure placeholders. The literature window is the user's (--window) or, when the user gave
none, the last five years [Y-5, Y]; it is written to the protocol as "Literature window: Y0-Y1" and read
back by the other scripts. Existing files are never overwritten, so it is safe to re-run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litrev_common import FILES, HEADERS, parse_window, slugify, write_csv  # noqa: E402

MODES = ("comprehensive", "rapid", "update")

PROTOCOL = {
    "en": """# Protocol — {title}

Status: Stage 0 — protocol draft
Mode: {mode} · Output language: {lang} · Created: {today}

## Intake — step 1: the research question (user's words)
- Research question:
- Literature window: {y0}-{y1} ({window_note})

## Intake — step 2: details
- Topic / working title:
- Dependent variable(s) and key regressors:
- Data, frequency, sample period:
- Countries / regions:
- Methods of interest (econometric, ML/AI, comparison):
- Known key papers (become seeds if published inside the window):
- Databases and tools the user can access (WoS, Scopus, ScienceDirect, Elicit, Consensus, Zotero, API keys):
- Output: chat summaries with links (always) · report: none / DOCX / PDF / both · language:

## Research question(s)
- RQ1 (main):
- RQ2 (mechanism / channel):
- RQ3 (heterogeneity: where, when, for whom):
- RQ4 (methods: how is it identified, and does the method change the answer?):

## PECO
- Population / context (P):
- Exposure / policy / shock (E):
- Comparator (C):
- Outcome(s) (O):
- Designs that count as evidence:

## Inclusion criteria
- I1: Published (journal, working paper, policy series) in {y0}-{y1}
- I2:

## Exclusion criteria (codes used in 04_screening.csv)
- E1: Off topic
- E2: Population, country or period out of scope
- E3: Ineligible design (e.g. purely descriptive for a causal question)
- E4: Another report of the same study (WP <-> journal)
- E5: Full text not retrievable
- E6: Not a primary study (keep reviews in 01_evidence_scan.md)
- E7: Published outside the literature window {y0}-{y1} (cite classics as background, not as included studies)

## Sources, access and languages
- Indexes via API / MCP / connector (see references/source-access.md):
- Subscription databases via export files (WoS, Scopus, ScienceDirect):
- Working-paper and policy series:
- Regional sources:
- Languages searched:
- Snowballing (backward / forward), author chasing:

## Stopping rule (comprehensive mode)
- All planned source x concept-block queries run for {y0}-{y1}
- Backward and forward snowballing of the core set done
- Seed-set recall 100% (or each miss explained)
- Last 3 queries / snowball rounds added < 5% new included studies
- Every included study in the window has a complete card (study_cards.py check passes)

## Deliverable
- Chat: answer first, then study cards in batches (all included studies, each with its verified link)
- Report format and language:
- Citation style: APA 7
- Appendices: search log, verification log, PRISMA flow, evidence workbook

## Assumptions
-

## Checkpoints
- C1 (protocol):
- C2 (included set):
- C3 (answer and synthesis outline):
""",
    "tr": """# Protokol — {title}

Durum: Aşama 0 — protokol taslağı
Mod: {mode} · Çıktı dili: {lang} · Oluşturma: {today}

## Ön görüşme — 1. adım: araştırma sorusu (kullanıcının ifadesiyle)
- Araştırma sorusu:
- Literatür penceresi: {y0}-{y1} ({window_note})

## Ön görüşme — 2. adım: ayrıntılar
- Konu / çalışma başlığı:
- Bağımlı değişken(ler) ve temel açıklayıcı değişkenler:
- Veri, frekans, örneklem dönemi:
- Ülkeler / bölgeler:
- İlgilenilen yöntemler (ekonometrik, ML/YZ, karşılaştırma):
- Bilinen temel çalışmalar (pencere içindeyse tohum olur):
- Kullanıcının erişebildiği veri tabanları ve araçlar (WoS, Scopus, ScienceDirect, Elicit, Consensus, Zotero, API anahtarları):
- Çıktı: bağlantılı sohbet özetleri (her zaman) · rapor: yok / DOCX / PDF / ikisi · dil:

## Araştırma soruları
- AS1 (ana soru):
- AS2 (mekanizma / kanal):
- AS3 (heterojenlik: nerede, ne zaman, kimin için):
- AS4 (yöntem: nasıl tanımlanıyor, yöntem cevabı değiştiriyor mu?):

## PECO
- Bağlam / örneklem (P):
- Maruziyet / politika / şok (E):
- Karşılaştırma (C):
- Sonuç değişken(ler)i (O):
- Kanıt sayılan tasarımlar:

## Dahil etme ölçütleri
- I1: {y0}-{y1} arasında yayımlanmış (dergi, çalışma tebliği, politika serisi)
- I2:

## Dışlama ölçütleri (kodlar 04_screening.csv'de kullanılır)
- E1: Konu dışı
- E2: Kapsam dışı örneklem, ülke veya dönem
- E3: Uygun olmayan tasarım (örn. nedensel soru için yalnızca betimsel)
- E4: Aynı çalışmanın başka raporu (WP <-> dergi)
- E5: Tam metne erişilemedi
- E6: Birincil çalışma değil (derlemeler 01_evidence_scan.md'de tutulur)
- E7: Literatür penceresi ({y0}-{y1}) dışında yayımlanmış (klasikler dahil edilen çalışma değil, arka plan kaynağı olarak anılır)

## Kaynaklar, erişim ve diller
- API / MCP / bağlayıcı ile taranan dizinler (bkz. references/source-access.md):
- Dışa aktarım dosyasıyla taranan abonelikli veri tabanları (WoS, Scopus, ScienceDirect):
- Çalışma tebliği ve politika serileri:
- Bölgesel kaynaklar:
- Taranan diller:
- Kartopu (geriye / ileriye), yazar takibi:

## Durdurma kuralı (kapsamlı mod)
- {y0}-{y1} için planlanan tüm kaynak x kavram bloğu sorguları çalıştırıldı
- Çekirdek setin geriye ve ileriye kartopu taraması yapıldı
- Tohum seti yakalama oranı %100 (ya da her eksik açıklandı)
- Son 3 sorgu / kartopu turu dahil edilen çalışmalara < %5 yeni katkı yaptı
- Penceredeki her dahil çalışmanın kartı tamam (study_cards.py check geçti)

## Teslim
- Sohbet: önce cevap, sonra bölümler hâlinde çalışma kartları (tüm dahil çalışmalar, her biri doğrulanmış bağlantısıyla)
- Rapor biçimi ve dili:
- Atıf stili: APA 7
- Ekler: arama günlüğü, doğrulama günlüğü, PRISMA akışı, kanıt çalışma kitabı

## Varsayımlar
-

## Kontrol noktaları
- C1 (protokol):
- C2 (dahil edilen set):
- C3 (cevap ve sentez taslağı):
""",
}

WINDOW_NOTE = {
    "en": {"user": "set by the user", "default": "default: last five years — no window was given"},
    "tr": {"user": "kullanıcı belirledi", "default": "varsayılan: son beş yıl — pencere belirtilmedi"},
}

REPORT = {
    "en": """<!-- Report skeleton. Replace every comment with prose; keep or delete placeholders.
     Build with: python3 scripts/build_report.py <folder> --format both --lang en -->

# Answer in brief

<!-- 4-8 sentences that answer RQ1 directly, with the strength of the evidence and the numbered cards it rests on. -->

{{TALLY}}

# 1. Research question and scope

<!-- RQ in the user's words, literature window, inclusion rules, sources searched. -->

{{FIGURE:pipeline}}

# 2. Search and selection

<!-- Sources and queries (table), records found, screening, verification. -->

{{FIGURE:prisma}}

{{FIGURE:sources}}

# 3. Shape of the literature

{{FIGURE:years}}

{{FIGURE:map}}

{{FIGURE:regions}}

# 4. Findings by theme

<!-- One subsection per theme: what the studies find, where they agree or disagree, and why (sample, method, period). -->

# 5. Weaknesses across the literature

<!-- Patterns, not a list: which weaknesses recur, which matter most for the answer. -->

{{FIGURE:weaknesses}}

{{WEAKNESS_TABLE}}

# 6. Research gaps and how your study can fill them

# 7. Limitations of this review

{{CARDS}}

{{REFERENCES}}
""",
    "tr": """<!-- Rapor iskeleti. Her yorumu metinle değiştirin; yer tutucuları tutun ya da silin.
     Derleme: python3 scripts/build_report.py <klasör> --format both --lang tr -->

# Kısa cevap

<!-- AS1'i doğrudan cevaplayan 4-8 cümle; kanıtın gücü ve dayandığı numaralı kartlar. -->

{{TALLY}}

# 1. Araştırma sorusu ve kapsam

<!-- Kullanıcının ifadesiyle AS, literatür penceresi, dahil etme kuralları, taranan kaynaklar. -->

{{FIGURE:pipeline}}

# 2. Tarama ve seçim

<!-- Kaynaklar ve sorgular (tablo), bulunan kayıtlar, eleme, doğrulama. -->

{{FIGURE:prisma}}

{{FIGURE:sources}}

# 3. Literatürün görünümü

{{FIGURE:years}}

{{FIGURE:map}}

{{FIGURE:regions}}

# 4. Temalara göre bulgular

<!-- Her tema için bir alt bölüm: çalışmalar ne buluyor, nerede ayrışıyor ve neden (örneklem, yöntem, dönem). -->

# 5. Literatürün zayıf yönleri

<!-- Liste değil örüntü: hangi zayıflıklar tekrarlanıyor, hangileri cevabı en çok etkiliyor. -->

{{FIGURE:weaknesses}}

{{WEAKNESS_TABLE}}

# 6. Araştırma boşlukları ve çalışmanın katkı alanı

# 7. Bu taramanın sınırlılıkları

{{CARDS}}

{{REFERENCES}}
""",
}

STUBS = {
    FILES["evidence_scan"]: "# Evidence scan — prior reviews, meta-analyses, surveys\n\n"
                            "| Review | Type | Search end date | Scope | Main conclusion | How this review builds on it |\n"
                            "|---|---|---|---|---|---|\n",
    FILES["synthesis"]: "# Synthesis\n\n",
    FILES["gaps"]: "# Research gaps\n\n",
    FILES["qa_log"]: "# QA log\n\n",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title", help="short review title")
    ap.add_argument("--mode", choices=MODES, default="comprehensive")
    ap.add_argument("--lang", default="en", help="output language code, e.g. en, tr, es (default en)")
    ap.add_argument("--window", default="", help="publication years, e.g. 2020-2026 or 2020-present "
                                                 "(default: the last five years)")
    ap.add_argument("--dir", default=".", help="parent directory (default: current)")
    args = ap.parse_args(argv)

    try:
        y0, y1 = parse_window(args.window)
    except ValueError as e:
        print(f"Error: {e}")
        return 2
    lang = args.lang.lower()[:2]
    tpl_lang = lang if lang in PROTOCOL else "en"
    folder = Path(args.dir) / f"litrev-{slugify(args.title)}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FILES["meta_dir"]).mkdir(exist_ok=True)
    (folder / FILES["figures_dir"]).mkdir(exist_ok=True)
    created, kept = [], []

    def make(name: str, writer) -> None:
        path = folder / name
        if path.exists():
            kept.append(name)
        else:
            writer(path)
            created.append(name)

    note = WINDOW_NOTE[tpl_lang]["user" if args.window.strip() else "default"]
    make(FILES["protocol"], lambda p: p.write_text(PROTOCOL[tpl_lang].format(
        title=args.title, mode=args.mode, lang=args.lang, today=dt.date.today().isoformat(),
        y0=y0, y1=y1, window_note=note), encoding="utf-8"))
    for name, header in HEADERS.items():
        make(name, lambda p, h=header: write_csv(p, [], h))
    for name, text in STUBS.items():
        make(name, lambda p, t=text: p.write_text(t, encoding="utf-8"))
    make(FILES["report_md"], lambda p: p.write_text(REPORT[tpl_lang], encoding="utf-8"))

    print(f"Folder: {folder}")
    print(f"Literature window: {y0}-{y1} ({WINDOW_NOTE['en']['user' if args.window.strip() else 'default']})")
    print("Created: " + (", ".join(created) or "-"))
    if kept:
        print("Kept existing: " + ", ".join(kept))
        if "00_protocol.md" in kept and args.window.strip():
            print("Note: the protocol already existed - edit its 'Literature window' line if the window changed.")
    if lang not in PROTOCOL:
        print(f"Note: no '{args.lang}' template - English protocol written; translate headings as needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
