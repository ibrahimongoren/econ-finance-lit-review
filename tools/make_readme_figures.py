#!/usr/bin/env python3
"""Draw the README figures: SVG diagrams in light and dark versions, plus the report preview.

Usage (from the repository root):
    python tools/make_readme_figures.py              # Figures 1-4 -> docs/assets/*.svg
    python tools/make_readme_figures.py --preview    # also Figure 5 (report preview PNG); needs matplotlib,
                                                     # python-docx, pandoc, LibreOffice, pdftoppm and Pillow
    python tools/make_readme_figures.py --lang en,tr # add Turkish versions for localized documentation

The diagrams are plain SVG (no scripts, no external fonts) so GitHub renders them as images; the README
picks the light or dark file with <picture> and prefers-color-scheme. The report preview is built from the
synthetic test data in tests/demo_data.py (fictional studies) and is labeled as such.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets"
FONT = "Arial, Helvetica, 'Liberation Sans', sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"

THEMES = {
    "light": {"panel": "#ffffff", "panel2": "#f6f8fa", "stroke": "#d0d7de", "ink": "#1f2328", "ink2": "#59636e",
              "muted": "#8c959f", "arrow": "#8c959f",
              "blue": "#2a78d6", "orange": "#e05a24", "green": "#13945f", "purple": "#6250d6", "red": "#d1242f",
              "amber": "#b7791f"},
    "dark": {"panel": "#161b22", "panel2": "#0d1117", "stroke": "#3d444d", "ink": "#f0f6fc", "ink2": "#9198a1",
             "muted": "#6e7681", "arrow": "#7d8590",
             "blue": "#4c94ea", "orange": "#f0834f", "green": "#35c48d", "purple": "#9d8cff", "red": "#ff6b6b",
             "amber": "#e3b341"},
}

# Arial advance widths (1/1000 em) for wrapping; unknown characters count as 600.
_W = {" ": 278, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556, "h": 556, "i": 222,
      "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556, "q": 556, "r": 333, "s": 500,
      "t": 278, "u": 556, "v": 500, "w": 722, "x": 500, "y": 500, "z": 500, "ı": 222, "ç": 500, "ş": 500,
      "ğ": 556, "ö": 556, "ü": 556, "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
      "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778,
      "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611, "İ": 278,
      "Ç": 722, "Ş": 667, "Ğ": 778, "Ö": 778, "Ü": 722, ".": 278, ",": 278, ":": 278, ";": 278, "-": 333,
      "–": 556, "—": 1000, "(": 333, ")": 333, "/": 278, "&": 667, "'": 191, '"': 355, "·": 278, "→": 1000,
      "±": 584, "×": 584, "?": 556, "!": 278, "+": 584, "|": 260, "*": 389, "_": 556, "=": 584, "#": 556,
      "[": 278, "]": 278, "…": 1000, "≤": 584, "✓": 750, "↻": 900}


def text_width(s: str, size: float, bold: bool = False) -> float:
    w = sum(_W.get(ch, 556 if ch.isdigit() else 600) for ch in s) / 1000 * size
    return w * (1.07 if bold else 1.0)


def wrap(s: str, size: float, width: float, bold: bool = False) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if text_width(trial, size, bold) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def up(s: str, lang: str) -> str:
    """Upper case that respects Turkish dotted and dotless i."""
    return (s.replace("i", "İ").replace("ı", "I") if lang == "tr" else s).upper()


def mix(c1: str, c2: str, t: float) -> str:
    """Blend color c1 into c2 by t (0 = c2, 1 = c1)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(a, b))


class Svg:
    def __init__(self, w: int, h: int, theme: str, title: str):
        self.w, self.h, self.t, self.parts = w, h, THEMES[theme], []
        self.title = title
        self.markers = {}

    def marker(self, color: str) -> str:
        if color not in self.markers:
            self.markers[color] = f"ah{len(self.markers)}"
        return self.markers[color]

    def add(self, s: str):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, stroke=None, r=8, sw=1.0, dash=None):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}"{st}{da}/>')

    def text(self, x, y, s, size=12, color=None, bold=False, anchor="start", italic=False, font=FONT):
        weight = ' font-weight="700"' if bold else ""
        style = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}"{weight}{style} '
                 f'fill="{color or self.t["ink"]}" text-anchor="{anchor}">{escape(s)}</text>')

    def lines(self, x, y, lines, size=12, color=None, bold=False, lh=None, anchor="start"):
        lh = lh or size * 1.32
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, size, color, bold, anchor)
        return y + len(lines) * lh

    def arrow(self, x1, y1, x2, y2, color=None, sw=1.4, dash=None):
        c = color or self.t["arrow"]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{sw}"'
                 f'{da} marker-end="url(#{self.marker(c)})"/>')

    def path(self, d, color, sw=1.4, arrow=True, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#{self.marker(color)})"' if arrow else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{me}/>')

    def circle(self, cx, cy, r, fill, stroke=None):
        st = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{st}/>')

    def render(self) -> str:
        defs = "".join(f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                       f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>'
                       for col, mid in self.markers.items())
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
                f'height="{self.h}" role="img" aria-label="{escape(self.title)}">\n<title>{escape(self.title)}</title>\n'
                f'<defs>{defs}</defs>\n')
        return head + "\n".join(self.parts) + "\n</svg>\n"


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
L = {
    "en": {
        "f1_title": "Figure 1. Review pipeline: intake and stages 0-10 in four phases",
        "phases": [("I", "Define"), ("II", "Find"), ("III", "Verify and read"), ("IV", "Synthesize and deliver")],
        "stages": [
            ("Q", "Intake", "Research question first, then the details"),
            ("0", "Protocol, window", "PECO, criteria E1–E7; the last five years by default"),
            ("1", "Prior reviews, seeds", "Surveys and meta-analyses; 5–15 seed papers to test recall"),
            ("2", "Search strategy", "One Boolean master query, translated for each database"),
            ("3", "Search", "APIs, connectors, exports, web, snowballing — until saturation"),
            ("4", "Screening", "Window filter (E7), kappa check, PRISMA 2020 flow"),
            ("5", "Verification", "Four-part registry match and a checked link for every study"),
            ("6", "Study cards", "Three passes; what it did, what it left out, weaknesses"),
            ("7", "Appraisal", "Credibility scored 0–2 on six dimensions"),
            ("8", "Synthesis", "Argument-led themes and certainty-graded answers"),
            ("9", "Research gaps", "Built from what studies leave out, each with a design"),
            ("10", "Delivery", "Every card in the chat; DOCX/PDF report; audits"),
        ],
        "f1_note": "Every stage writes a numbered file (00_protocol.md … 10_report.*), so a review can pause and resume.",
        "f2_title": "Figure 2. Search architecture: one strategy, four routes, one screened record set",
        "query": "Research question  →  concept blocks  →  one Boolean master query",
        "query2": "translated per database: WoS  TS=(…) AND PY=(…) · Scopus  TITLE-ABS-KEY(…) · Semantic Scholar  + | - · OpenAlex · arXiv",
        "routes": [
            ("A", "API scripts", "search_sources.py", [("OpenAlex", 0), ("Crossref", 0), ("Semantic Scholar", 0),
                                                       ("arXiv", 0), ("Unpaywall", 0), ("Scopus", 1),
                                                       ("ScienceDirect", 1), ("Web of Science", 1),
                                                       ("Google Scholar (SerpApi)", 1)]),
            ("B", "Connectors and MCP", "Claude apps · Claude Code", [("Consensus", 0), ("SciSpace", 0), ("Elicit", 1),
                                                                      ("paper-search-mcp", 0), ("arxiv-mcp-server", 0),
                                                                      ("Zotero", 0)]),
            ("C", "Database exports", "import_records.py", [("Web of Science", 1), ("Scopus", 1), ("ScienceDirect", 1),
                                                           ("Publish or Perish", 0), ("Zotero", 0),
                                                           ("RIS · BibTeX · CSV · JSON", 0)]),
            ("D", "Web search and fetch", "working papers · policy", [("NBER", 0), ("CEPR", 0), ("BIS", 0), ("IMF", 0),
                                                                      ("ECB", 0), ("Fed", 0), ("World Bank", 0),
                                                                      ("OECD", 0), ("central banks", 0), ("RePEc", 0),
                                                                      ("DergiPark", 0)]),
        ],
        "snow": "+ backward and forward snowballing, author chasing, a recency sweep of the last 18 months",
        "chain": ["Records per source", "De-duplication", "Window filter (E7)", "Screening", "PRISMA 2020 flow"],
        "legend_free": "open / free", "legend_key": "key, subscription or paid plan",
        "f3_title": "Figure 3. Three-pass reading: from the paper to the study card",
        "paper": "Paper",
        "sections": [("Abstract", 1), ("Introduction", 2), ("Literature review", 3), ("Data and methodology", 2),
                     ("Results, tables", 0), ("Conclusion", 1)],
        "passes": [("Pass 1", "Abstract → Conclusion", "Question, sample, method, main result (sign, size, units); do the conclusions match the evidence?"),
                   ("Pass 2", "Introduction → Methodology", "Claimed contribution, specification, identification, data, estimation, robustness."),
                   ("Pass 3", "Literature review", "Strands and key works it builds on, the gap it claims, what it does not engage with.")],
        "card": "Study card", "card_head": "[n]  Author (Year) — Title of the study",
        "card_meta": "Journal · doi.org link · ✓ verified · [FT]",
        "card_rows": [("WHAT DID IT DO?", "question → data → method → finding → contribution"),
                      ("WHAT DID IT LEAVE OUT?", "variables, channels, countries, periods, methods"),
                      ("WEAKNESSES", "category · severity · location · basis"),
                      ("RELEVANCE", "contribution to the user's own research")],
        "card_example": "[Identification · high] expectations assumed exogenous (Sec. 3.2)",
        "f4_title": "Figure 4. Verification: ladder, checks and status of every reference",
        "lead": "Lead from any route",
        "ladder_title": "Ladder — stop at the first rung that matches",
        "rungs": [("1", "DOI record", "Crossref · OpenAlex", "High"),
                  ("2", "Official landing page", "publisher · series page", "High"),
                  ("3", "Index page", "RePEc · Semantic Scholar · SSRN", "Medium–High"),
                  ("4", "Search snippet only", "result list", "≤ PARTIAL")],
        "checks_title": "Checks",
        "checks": [("Match test — all four", "title · first author · year ±1 · venue"),
                   ("Link check", "doi.org handle API, or the page shows the title"),
                   ("Integrity", "retraction · front matter · version")],
        "status_title": "Status",
        "statuses": [("VERIFIED", "green", "record, match, link"), ("PARTIAL", "amber", "one field disputed"),
                     ("PREPRINT", "blue", "working paper"), ("NOT_VERIFIED", "muted", "listed, never evidence"),
                     ("RETRACTED", "red", "removed")],
        "printed": "printed and used", "not_printed": "never used as evidence",
    },
    "tr": {
        "f1_title": "Şekil 1. Tarama süreci: ön görüşme ve 0-10 arası aşamalar, dört evrede",
        "phases": [("I", "Tanımla"), ("II", "Bul"), ("III", "Doğrula ve oku"), ("IV", "Sentezle ve sun")],
        "stages": [
            ("Q", "Ön görüşme", "Önce araştırma sorusu, sonra ayrıntılar"),
            ("0", "Protokol, pencere", "PECO, ölçütler E1–E7; yıl verilmezse son beş yıl"),
            ("1", "Derlemeler, tohumlar", "Derleme ve meta-analizler; aramayı sınayan 5–15 tohum çalışma"),
            ("2", "Arama stratejisi", "Her veri tabanına çevrilen tek bir Boole ana sorgusu"),
            ("3", "Tarama", "API, bağlayıcı, dışa aktarım, web, kartopu — doygunluğa dek"),
            ("4", "Eleme", "Pencere filtresi (E7), kappa tutarlılık testi, PRISMA 2020"),
            ("5", "Doğrulama", "Dört ölçütlü kayıt eşleşmesi ve her çalışma için denetlenmiş bağlantı"),
            ("6", "Çalışma kartları", "Üç tur; ne yapmış, neyi eksik bırakmış, zayıf yönler"),
            ("7", "Değerlendirme", "Altı boyutta 0–2 güvenilirlik puanı"),
            ("8", "Sentez", "Argümana dayalı temalar, kesinlik dereceli cevaplar"),
            ("9", "Boşluklar", "Çalışmaların eksik bıraktıklarından, tasarımlarıyla"),
            ("10", "Teslim", "Tüm kartlar sohbette; DOCX/PDF rapor; denetimler"),
        ],
        "f1_note": "Her aşama numaralı bir dosya yazar (00_protocol.md … 10_report.*); tarama durdurulup sürdürülebilir.",
        "f2_title": "Şekil 2. Tarama mimarisi: tek strateji, dört yol, elenmiş tek kayıt kümesi",
        "query": "Araştırma sorusu  →  kavram blokları  →  tek bir Boole ana sorgusu",
        "query2": "her veri tabanına çevrilir: WoS  TS=(…) AND PY=(…) · Scopus  TITLE-ABS-KEY(…) · Semantic Scholar  + | - · OpenAlex · arXiv",
        "routes": [
            ("A", "API betikleri", "search_sources.py", [("OpenAlex", 0), ("Crossref", 0), ("Semantic Scholar", 0),
                                                         ("arXiv", 0), ("Unpaywall", 0), ("Scopus", 1),
                                                         ("ScienceDirect", 1), ("Web of Science", 1),
                                                         ("Google Scholar (SerpApi)", 1)]),
            ("B", "Bağlayıcılar ve MCP", "Claude uygulamaları · Claude Code", [("Consensus", 0), ("SciSpace", 0),
                                                                                ("Elicit", 1), ("paper-search-mcp", 0),
                                                                                ("arxiv-mcp-server", 0), ("Zotero", 0)]),
            ("C", "Dışa aktarımlar", "import_records.py", [("Web of Science", 1), ("Scopus", 1), ("ScienceDirect", 1),
                                                          ("Publish or Perish", 0), ("Zotero", 0),
                                                          ("RIS · BibTeX · CSV · JSON", 0)]),
            ("D", "Web araması ve getirme", "çalışma tebliğleri · politika", [("NBER", 0), ("CEPR", 0), ("BIS", 0),
                                                                              ("IMF", 0), ("ECB", 0), ("Fed", 0),
                                                                              ("Dünya Bankası", 0), ("OECD", 0),
                                                                              ("merkez bankaları", 0), ("RePEc", 0),
                                                                              ("DergiPark", 0)]),
        ],
        "snow": "+ geriye ve ileriye kartopu taraması, yazar takibi, son 18 ayın güncellik taraması",
        "chain": ["Kaynak başına kayıtlar", "Mükerrer ayıklama", "Pencere filtresi (E7)", "Eleme", "PRISMA 2020 akışı"],
        "legend_free": "açık / ücretsiz", "legend_key": "anahtar, abonelik ya da ücretli plan",
        "f3_title": "Şekil 3. Üç turlu okuma: makaleden çalışma kartına",
        "paper": "Makale",
        "sections": [("Özet", 1), ("Giriş", 2), ("Literatür taraması", 3), ("Veri ve yöntem", 2),
                     ("Bulgular, tablolar", 0), ("Sonuç", 1)],
        "passes": [("1. tur", "Özet → Sonuç", "Soru, örneklem, yöntem, temel bulgu (işaret, büyüklük, birim); sonuçlar kanıtla örtüşüyor mu?"),
                   ("2. tur", "Giriş → Yöntem", "İddia edilen katkı, model kurgusu, tanımlama, veri, tahmin, sağlamlık."),
                   ("3. tur", "Literatür taraması", "Dayandığı yazın ve temel çalışmalar, iddia ettiği boşluk, ele almadıkları.")],
        "card": "Çalışma kartı", "card_head": "[n]  Yazar (Yıl) — Çalışmanın başlığı",
        "card_meta": "Dergi · doi.org bağlantısı · ✓ doğrulandı · [FT]",
        "card_rows": [("NE YAPMIŞ?", "soru → veri → yöntem → bulgu → katkı"),
                      ("NEYİ EKSİK BIRAKMIŞ?", "değişkenler, kanallar, ülkeler, dönemler, yöntemler"),
                      ("ZAYIF YÖNLER", "kategori · şiddet · konum · dayanak"),
                      ("ÇALIŞMANA KATKISI", "çalışmanıza nasıl hizmet ettiği")],
        "card_example": "[Tanımlama · yüksek] dışsal beklentiler (Böl. 3.2)",
        "f4_title": "Şekil 4. Doğrulama: merdiven, denetimler ve her kaynağın durumu",
        "lead": "Herhangi bir yoldan gelen kayıt",
        "ladder_title": "Merdiven — eşleşen ilk basamakta durulur",
        "rungs": [("1", "DOI kaydı", "Crossref · OpenAlex", "Yüksek"),
                  ("2", "Resmî sayfa", "yayıncı · seri sayfası", "Yüksek"),
                  ("3", "Dizin sayfası", "RePEc · Semantic Scholar · SSRN", "Orta–Yüksek"),
                  ("4", "Yalnızca arama özeti", "sonuç listesi", "≤ PARTIAL")],
        "checks_title": "Denetimler",
        "checks": [("Eşleşme testi — dördü birden", "başlık · ilk yazar · yıl ±1 · yayın yeri"),
                   ("Bağlantı kontrolü", "doi.org handle API ya da başlığı gösteren sayfa"),
                   ("Bütünlük", "geri çekilme · ön sayfa · sürüm")],
        "status_title": "Durum",
        "statuses": [("VERIFIED", "green", "kayıt, eşleşme, bağlantı"), ("PARTIAL", "amber", "bir alan tartışmalı"),
                     ("PREPRINT", "blue", "çalışma tebliği"), ("NOT_VERIFIED", "muted", "ayrı liste, kanıt değil"),
                     ("RETRACTED", "red", "çıkarılır")],
        "printed": "basılır ve kullanılır", "not_printed": "asla kanıt olarak kullanılmaz",
    },
}
PHASE_COLORS = ["blue", "orange", "green", "purple"]
PASS_COLORS = {1: "blue", 2: "orange", 3: "green", 0: "muted"}


# ---------------------------------------------------------------------------
# Figure 1 — pipeline
# ---------------------------------------------------------------------------
def fit(text, size, width, bold=False, floor=10.0):
    """Largest font size (down to floor) at which text fits the width."""
    while text_width(text, size, bold) > width and size > floor:
        size -= 0.25
    return size


def fig_pipeline(lang: str, theme: str) -> str:
    lb, W = L[lang], 920
    pw, gap = 215, 20
    bh, bgap, head = 108, 14, 52
    ph = head + 3 * bh + 2 * bgap + 14
    H = ph + 2
    s = Svg(W, H, theme, lb["f1_title"])
    t = s.t
    for k, (num, name) in enumerate(lb["phases"]):
        x = k * (pw + gap)
        col = t[PHASE_COLORS[k]]
        s.rect(x, 0, pw, ph, t["panel2"], t["stroke"], r=10)
        s.rect(x, 0, pw, 5, col, None, r=2)
        s.text(x + 14, 30, num, 12.5, col, bold=True)
        label = up(name, lang)
        s.text(x + 14 + text_width(num, 12.5, True) + 8, 30,
               label, fit(label, 12.5, pw - 40 - text_width(num, 12.5, True), True), t["ink2"], bold=True)
        if k < 3:
            s.arrow(x + pw + 3, 25, x + pw + gap - 3, 25)
        for j in range(3):
            num_s, title, detail = lb["stages"][k * 3 + j]
            bx, by, bw = x + 12, head + j * (bh + bgap), pw - 24
            s.rect(bx, by, bw, bh, t["panel"], t["stroke"], r=8)
            s.circle(bx + 21, by + 23, 13.5, mix(col, t["panel"], 0.16), col)
            s.text(bx + 21, by + 28, num_s, 12.5 if len(num_s) < 2 else 11, col, bold=True, anchor="middle")
            s.text(bx + 42, by + 28.5, title, fit(title, 15, bw - 48, True, 12), t["ink"], bold=True)
            s.lines(bx + 12, by + 57, wrap(detail, 13, bw - 30)[:3], 13, t["ink2"], lh=17)
            if j < 2:
                s.arrow(bx + bw / 2, by + bh + 1.5, bx + bw / 2, by + bh + bgap - 1.5)
    return s.render()


# ---------------------------------------------------------------------------
# Figure 2 — search architecture
# ---------------------------------------------------------------------------
CHIP = 12.5


def chip_rows(chips, width, size=CHIP, pad=8, gap=6):
    rows, cur, curw = [], [], 0
    for label, kind in chips:
        w = text_width(label, size) + 2 * pad
        if cur and curw + gap + w > width:
            rows.append(cur)
            cur, curw = [], 0
        cur.append((label, kind, w))
        curw += (gap if curw else 0) + w
    if cur:
        rows.append(cur)
    return rows


def fig_search(lang: str, theme: str) -> str:
    lb, W = L[lang], 920
    t = THEMES[theme]
    pw, gap, q_h = 215, 20, 68
    routes_y = q_h + 34
    layouts = [chip_rows(chips, pw - 24) for *_, chips in lb["routes"]]
    panel_h = 72 + max(len(r) for r in layouts) * 31 + 8
    snow_y = routes_y + panel_h + 12
    chain_y = snow_y + 34 + 34
    H = chain_y + 44 + 46
    s = Svg(W, H, theme, lb["f2_title"])
    s.rect(0, 0, W, q_h, t["panel"], t["stroke"], r=10)
    s.text(W / 2, 28, lb["query"], fit(lb["query"], 15.5, W - 30, True), t["ink"], bold=True, anchor="middle")
    s.text(W / 2, 52, lb["query2"], fit(lb["query2"], 12.5, W - 30, floor=10.5), t["ink2"], anchor="middle")
    for k, ((letter, name, sub, chips), rows) in enumerate(zip(lb["routes"], layouts)):
        x = k * (pw + gap)
        col = t[PHASE_COLORS[k]]
        s.arrow(x + pw / 2, q_h + 2, x + pw / 2, routes_y - 3)
        s.rect(x, routes_y, pw, panel_h, t["panel2"], t["stroke"], r=10)
        s.rect(x, routes_y, pw, 5, col, None, r=2)
        s.circle(x + 25, routes_y + 32, 13.5, mix(col, t["panel"], 0.16), col)
        s.text(x + 25, routes_y + 37, letter, 13, col, bold=True, anchor="middle")
        s.text(x + 46, routes_y + 31, name, fit(name, 15, pw - 56, True, 12), t["ink"], bold=True)
        mono = sub.endswith(".py")
        s.text(x + 46, routes_y + 50, sub, fit(sub, 12, pw - 56, floor=9.5) if not mono else 11.5, t["ink2"],
               font=MONO if mono else FONT)
        cy = routes_y + 68
        for row in rows:
            cx = x + 12
            for label, kind, w in row:
                if kind:
                    s.rect(cx, cy, w, 25, t["panel"], t["ink2"], r=12.5, sw=1, dash="3 2.5")
                else:
                    s.rect(cx, cy, w, 25, mix(col, t["panel"], 0.12), mix(col, t["panel"], 0.55), r=12.5, sw=1)
                s.text(cx + w / 2, cy + 17, label, CHIP, t["ink"], anchor="middle")
                cx += w + 6
            cy += 31
        s.arrow(x + pw / 2, routes_y + panel_h + 1, x + pw / 2, snow_y - 2)
    s.rect(0, snow_y, W, 34, t["panel"], t["stroke"], r=8, dash="4 3")
    s.text(W / 2, snow_y + 22, lb["snow"], fit(lb["snow"], 13, W - 30), t["ink2"], anchor="middle", italic=True)
    n, cgap = len(lb["chain"]), 24
    cw = (W - (n - 1) * cgap) / n
    s.arrow(cw / 2, snow_y + 35, cw / 2, chain_y - 3)
    for i, label in enumerate(lb["chain"]):
        cx = i * (cw + cgap)
        last = i == n - 1
        s.rect(cx, chain_y, cw, 44, mix(t["blue"], t["panel"], 0.14) if last else t["panel"],
               t["blue"] if last else t["stroke"], r=8)
        s.text(cx + cw / 2, chain_y + 27, label, fit(label, 14, cw - 14, True, 11), t["ink"], bold=True, anchor="middle")
        if i < n - 1:
            s.arrow(cx + cw + 3, chain_y + 22, cx + cw + cgap - 3, chain_y + 22)
    ly = chain_y + 78
    s.rect(0, ly - 15, 36, 20, mix(t["blue"], t["panel"], 0.12), mix(t["blue"], t["panel"], 0.55), r=10)
    s.text(46, ly, lb["legend_free"], 12.5, t["ink2"])
    lx = 46 + text_width(lb["legend_free"], 12.5) + 30
    s.rect(lx, ly - 15, 36, 20, t["panel"], t["ink2"], r=10, dash="3 2.5")
    s.text(lx + 46, ly, lb["legend_key"], 12.5, t["ink2"])
    return s.render()


# ---------------------------------------------------------------------------
# Figure 3 — three-pass reading
# ---------------------------------------------------------------------------
def fig_reading(lang: str, theme: str) -> str:
    lb, W = L[lang], 920
    t = THEMES[theme]
    cx = 584
    cw = W - cx
    rows = []
    for i, (label, desc) in enumerate(lb["card_rows"]):
        d_lines = wrap(desc, 13, cw - 58)
        h = 32 + len(d_lines) * 17 + (34 if i == 2 else 0) + 6
        rows.append((label, d_lines, h))
    card_h = 92 + sum(h + 8 for *_, h in rows) + 6
    sec_h, sec_gap = 44, 8
    paper_h = 48 + len(lb["sections"]) * (sec_h + sec_gap) + 6
    H = int(max(card_h, paper_h)) + 4
    s = Svg(W, H, theme, lb["f3_title"])
    px, py, pw = 0, (H - 4 - paper_h) / 2, 200
    s.rect(px, py, pw, paper_h, t["panel2"], t["stroke"], r=10)
    s.text(px + 16, py + 30, up(lb["paper"], lang), 12.5, t["ink2"], bold=True)
    sec_mid = {}
    for i, (name, p) in enumerate(lb["sections"]):
        y = py + 48 + i * (sec_h + sec_gap)
        col = t[PASS_COLORS[p]] if p else t["muted"]
        s.rect(px + 12, y, pw - 24, sec_h, t["panel"], t["stroke"], r=6)
        s.rect(px + 12, y, 6, sec_h, col, None, r=2)
        s.text(px + 28, y + 27.5, name, fit(name, 14, pw - 50, bool(p)), t["ink"] if p else t["ink2"], bold=bool(p))
        sec_mid.setdefault(p, []).append(y + sec_h / 2)
    bx, bw, bh = 246, 300, 104
    gap = (H - 4 - 3 * bh) / 2
    for k, (tag, title, desc) in enumerate(lb["passes"]):
        p = k + 1
        col = t[PASS_COLORS[p]]
        y = k * (bh + gap)
        s.rect(bx, y, bw, bh, t["panel"], col, r=9, sw=1.5)
        tag_u = up(tag, lang)
        s.text(bx + 14, y + 27, tag_u, 12.5, col, bold=True)
        tx = bx + 14 + text_width(tag_u, 12.5, True) + 9
        s.text(tx, y + 27, title, fit(title, 15, bx + bw - 12 - tx, True, 12), t["ink"], bold=True)
        s.lines(bx + 14, y + 52, wrap(desc, 13, bw - 36)[:3], 13, t["ink2"], lh=17)
        for ym in sec_mid.get(p, []):
            s.path(f"M{px + pw - 12},{ym:.1f} C{px + pw + 22},{ym:.1f} {bx - 26},{y + bh / 2:.1f} {bx - 2},{y + bh / 2:.1f}",
                   col, sw=1.6)
    s.rect(cx, 0, cw, card_h, t["panel"], t["stroke"], r=10)
    s.rect(cx, 0, cw, 5, t["blue"], None, r=2)
    s.text(cx + 16, 29, up(lb["card"], lang), 12.5, t["ink2"], bold=True)
    s.text(cx + 16, 54, lb["card_head"], fit(lb["card_head"], 14.5, cw - 32, True, 11.5), t["ink"], bold=True)
    s.text(cx + 16, 74, lb["card_meta"], fit(lb["card_meta"], 12.5, cw - 32), t["ink2"])
    y = 92
    for i, (label, d_lines, h) in enumerate(rows):
        col = [t["blue"], t["orange"], t["red"], t["green"]][i]
        s.rect(cx + 14, y, cw - 28, h, t["panel2"], t["stroke"], r=7)
        s.rect(cx + 14, y, 4, h, col, None, r=2)
        s.text(cx + 30, y + 23, label, 13, t["ink"], bold=True)
        yy = s.lines(cx + 30, y + 43, d_lines, 13, t["ink2"], lh=17)
        if i == 2:
            ex = lb["card_example"]
            size = fit(ex, 12, cw - 78, floor=9.5)
            s.rect(cx + 30, yy - 5, text_width(ex, size) + 18, 25, mix(t["red"], t["panel"], 0.10),
                   mix(t["red"], t["panel"], 0.45), r=12.5)
            s.text(cx + 39, yy + 12, ex, size, t["ink"])
        y += h + 8
    mid = bh + gap + bh / 2
    s.arrow(bx + bw + 6, mid, cx - 6, mid, sw=1.6)
    return s.render()


# ---------------------------------------------------------------------------
# Figure 4 — verification
# ---------------------------------------------------------------------------
def fig_verification(lang: str, theme: str) -> str:
    lb, W = L[lang], 920
    t = THEMES[theme]
    PH = 354
    H = PH + 2
    s = Svg(W, H, theme, lb["f4_title"])
    mid = PH / 2
    lead_lines = wrap(lb["lead"], 13.5, 94, bold=True)
    s.rect(0, mid - 42, 116, 84, t["panel2"], t["stroke"], r=9)
    s.lines(58, mid + 5 - (len(lead_lines) - 1) * 9, lead_lines, 13.5, t["ink"], bold=True, anchor="middle", lh=18)
    lx, lw = 138, 342
    s.rect(lx, 0, lw, PH, t["panel2"], t["stroke"], r=10)
    s.text(lx + 16, 29, lb["ladder_title"], fit(lb["ladder_title"], 13.5, lw - 32, True), t["ink2"], bold=True)
    s.arrow(118, mid, lx - 3, mid)
    for i, (n, name, how, conf) in enumerate(lb["rungs"]):
        y = 44 + i * 76
        s.rect(lx + 12, y, lw - 24, 68, t["panel"], t["stroke"], r=8)
        col = t["green"] if i < 2 else (t["amber"] if i == 2 else t["red"])
        s.circle(lx + 35, y + 34, 13.5, mix(col, t["panel"], 0.16), col)
        s.text(lx + 35, y + 39, n, 13, col, bold=True, anchor="middle")
        pw_ = text_width(conf, 12, True) + 18
        s.rect(lx + lw - 24 - pw_, y + 10, pw_, 24, mix(col, t["panel"], 0.12), mix(col, t["panel"], 0.5), r=12)
        s.text(lx + lw - 24 - pw_ / 2, y + 26.5, conf, 12, t["ink"], bold=True, anchor="middle")
        s.text(lx + 58, y + 28, name, fit(name, 15, lw - 24 - 58 - pw_ - 8, True, 12), t["ink"], bold=True)
        s.text(lx + 58, y + 52, how, fit(how, 13, lw - 24 - 58 - 8), t["ink2"])
    cx, cw = 502, 198
    s.rect(cx, 0, cw, PH, t["panel2"], t["stroke"], r=10)
    s.text(cx + 16, 29, lb["checks_title"], 13.5, t["ink2"], bold=True)
    s.arrow(lx + lw + 3, mid, cx - 3, mid)
    for i, (name, desc) in enumerate(lb["checks"]):
        y = 44 + i * 102
        s.rect(cx + 12, y, cw - 24, 94, t["panel"], t["stroke"], r=8)
        yy = s.lines(cx + 24, y + 24, wrap(name, 14, cw - 48, bold=True), 14, t["ink"], bold=True, lh=17)
        s.lines(cx + 24, yy + 4, wrap(desc, 12.5, cw - 46)[:3], 12.5, t["ink2"], lh=16)
    sx = 722
    sw_ = W - sx
    s.rect(sx, 0, sw_, PH, t["panel2"], t["stroke"], r=10)
    s.text(sx + 16, 29, lb["status_title"], 13.5, t["ink2"], bold=True)
    s.arrow(cx + cw + 3, mid, sx - 3, mid)
    y = 42
    for i, (code, colname, desc) in enumerate(lb["statuses"]):
        if i in (0, 3):
            label = up(lb["printed"] if i == 0 else lb["not_printed"], lang)
            s.text(sx + 14, y + 12, label, fit(label, 11, sw_ - 28, True, 8.5), t["ink2"], bold=True)
            y += 20
        col = t[colname] if colname != "muted" else t["ink2"]
        s.rect(sx + 12, y, sw_ - 24, 44, mix(col, t["panel"], 0.10), mix(col, t["panel"], 0.55), r=8)
        s.text(sx + 24, y + 19, code, 12.5, t["ink"], bold=True, font=MONO)
        s.text(sx + 24, y + 36, desc, fit(desc, 12.5, sw_ - 48, floor=10), t["ink2"])
        y += 50 + (8 if i == 2 else 0)
    return s.render()


FIGURES = {"fig1-pipeline": fig_pipeline, "fig2-search": fig_search, "fig3-reading": fig_reading,
           "fig4-verification": fig_verification}


# ---------------------------------------------------------------------------
# Figure 5 — report preview from synthetic data
# ---------------------------------------------------------------------------
TR_TEXT = {
    "Asks whether inflation persistence differs across regimes; finds higher persistence in the high-risk regime.":
        "Enflasyon kalıcılığının rejimlere göre farklılaşıp farklılaşmadığını sorar; yüksek risk rejiminde kalıcılığın daha yüksek olduğunu bulur.",
    "Two-regime Markov-switching hybrid NKPC, quarterly data, survey expectations.":
        "İki rejimli Markov geçişli hibrit YKPE; çeyreklik veri, anket beklentileri.",
    "Builds on hybrid NKPC work; positions against linear GMM estimates.":
        "Hibrit YKPE yazınına dayanır; doğrusal GMM tahminlerinin karşısında konumlanır.",
    "Estimates a regime-dependent hybrid Phillips curve with a risk index.":
        "Bir risk endeksiyle rejime bağlı hibrit Phillips eğrisi tahmin eder.",
    "No climate-risk channel; no out-of-sample comparison.":
        "İklim riski kanalı yok; örneklem dışı karşılaştırma yapılmamış.",
    "Direct benchmark for the user's regime-dependent specification.":
        "Rejime bağlı model kurgunuz için doğrudan karşılaştırma ölçütü.",
    "Expected inflation is treated as exogenous; no instrument for survey expectations.":
        "Beklenen enflasyon dışsal kabul edilmiş; anket beklentileri için araç değişken yok.",
    "Climate risk index is annual and interpolated to quarterly frequency.":
        "İklim riski endeksi yıllık; çeyreklik frekansa ara değerlemeyle çevrilmiş.",
    "Regime count fixed at two; no test against three regimes.":
        "Rejim sayısı ikiye sabitlenmiş; üç rejime karşı test edilmemiş.",
    "Single-country sample limits generalization to other emerging markets.":
        "Tek ülkelik örneklem, diğer gelişmekte olan ülkelere genellemeyi sınırlıyor.",
    "Weak-instrument diagnostics are not reported for the GMM estimates.":
        "GMM tahminleri için zayıf araç değişken tanıları raporlanmamış.",
    "Does not engage with recent nonlinear Phillips-curve evidence.":
        "Doğrusal olmayan Phillips eğrisi üzerine güncel bulgularla ilişki kurmuyor.",
    "Expectations and persistence": "Beklentiler ve kalıcılık",
    "Oil and exchange-rate pass-through": "Petrol ve kur geçişkenliği",
    "Geopolitical risk": "Jeopolitik risk", "Climate risk": "İklim riski", "Regime switching": "Rejim değişimi",
    "Journal of Testing": "Test Dergisi", "Test WP Series": "Test Çalışma Tebliği Serisi",
    "Section 3.2": "Bölüm 3.2", "Section 2": "Bölüm 2", "Data appendix": "Veri eki", "Table 4": "Tablo 4",
    "Table 2": "Tablo 2", "Conclusion": "Sonuç", "abstract": "özet",
    "Turkey": "Türkiye", "Brazil": "Brezilya", "Mexico": "Meksika", "South Africa": "Güney Afrika",
    "OECD panel": "OECD paneli", "Euro area": "Avro bölgesi", "Machine learning": "Makine öğrenmesi",
    "Local projections": "Yerel projeksiyonlar", "Quantile regression": "Kantil regresyon",
}
NARRATIVE = {
    "en": """# Answer in brief

*Illustrative layout built from synthetic test data (fictional studies); not a real review.*
Across the twelve synthetic studies, inflation persistence is higher in high-risk regimes [1, 4, 9], but most
estimates treat survey expectations as exogenous, which lowers certainty to **Low**.

{{TALLY}}

# 1. Research question and scope

{{FIGURE:pipeline}}

# 2. Search and selection

{{FIGURE:prisma}}

{{FIGURE:sources}}

# 3. Shape of the literature

{{FIGURE:years}}

{{FIGURE:map}}

{{FIGURE:regions}}

# 4. Weaknesses across the literature

{{FIGURE:weaknesses}}

{{WEAKNESS_TABLE}}

{{CARDS}}

{{REFERENCES}}
""",
    "tr": """# Kısa cevap

*Sentetik test verisinden (kurgusal çalışmalar) üretilmiş örnek düzen; gerçek bir tarama değildir.*
On iki sentetik çalışmada enflasyon kalıcılığı yüksek risk rejimlerinde daha yüksektir [1, 4, 9]; ancak
tahminlerin çoğu anket beklentilerini dışsal kabul ettiğinden kesinlik **Düşük** düzeydedir.

{{TALLY}}

# 1. Araştırma sorusu ve kapsam

{{FIGURE:pipeline}}

# 2. Tarama ve seçim

{{FIGURE:prisma}}

{{FIGURE:sources}}

# 3. Literatürün görünümü

{{FIGURE:years}}

{{FIGURE:map}}

{{FIGURE:regions}}

# 4. Literatürün zayıf yönleri

{{FIGURE:weaknesses}}

{{WEAKNESS_TABLE}}

{{CARDS}}

{{REFERENCES}}
""",
}
PREVIEW = {
    "en": {"title": "Regime-dependent hybrid Phillips curves", "subtitle": "Layout preview — synthetic test data",
           "labels": ["Cover and key facts", "Figures", "Weaknesses", "Study cards"]},
    "tr": {"title": "Rejime bağlı hibrit Phillips eğrileri", "subtitle": "Düzen önizlemesi — sentetik test verisi",
           "labels": ["Kapak ve temel bilgiler", "Şekiller", "Zayıf yönler", "Çalışma kartları"]},
}


def _localise_tr(folder: Path) -> None:
    sys.path.insert(0, str(ROOT / "skills" / "econ-finance-lit-review" / "scripts"))
    from litrev_common import FILES, HEADERS, read_csv, write_csv
    for key in ("cards", "weaknesses", "extraction", "verification"):
        path = folder / FILES[key]
        rows = read_csv(path)
        for r in rows:
            for k, v in r.items():
                if v in TR_TEXT:
                    r[k] = TR_TEXT[v]
                elif k == "title" and v.startswith("Synthetic study"):
                    n = re.search(r"\d+", v).group(0)
                    r[k] = f"Rejime bağlı hibrit Phillips eğrisi üzerine sentetik çalışma {n}"
                elif k == "country_region":
                    r[k] = ", ".join(TR_TEXT.get(x.strip(), x.strip()) for x in v.split(","))
                elif k == "method_family":
                    r[k] = TR_TEXT.get(v, v)
        write_csv(path, rows, HEADERS[FILES[key]])


def build_preview(lang: str) -> Path:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    scripts = ROOT / "skills" / "econ-finance-lit-review" / "scripts"
    sys.path.insert(0, str(scripts))
    sys.path.insert(0, str(ROOT / "tests"))
    from demo_data import build_demo
    work = Path(tempfile.mkdtemp(prefix="readme-preview-"))
    py = sys.executable
    subprocess.run([py, str(scripts / "init_review.py"), PREVIEW[lang]["title"], "--lang", lang, "--window",
                    "2021-2026", "--dir", str(work)], check=True, capture_output=True)
    folder = next(work.glob("litrev-*"))
    build_demo(folder)
    if lang == "tr":
        _localise_tr(folder)
    (folder / "10_report.md").write_text(NARRATIVE[lang], encoding="utf-8")
    for cmd in ([py, str(scripts / "dedupe_records.py"), str(folder)],
                [py, str(scripts / "screening_check.py"), "window", str(folder)],
                [py, str(scripts / "prisma_flow.py"), str(folder), "--lang", lang],
                [py, str(scripts / "build_report.py"), str(folder), "--format", "pdf", "--lang", lang,
                 "--subtitle", PREVIEW[lang]["subtitle"], "--author", "econ-finance-lit-review"]):
        subprocess.run(cmd, check=True, capture_output=True)
    pdf = folder / "10_report.pdf"
    subprocess.run(["pdftoppm", "-r", "80", "-png", str(pdf), str(work / "page")], check=True)
    pages = sorted(work.glob("page-*.png"))
    text = []
    for i in range(len(pages)):
        res = subprocess.run(["pdftotext", "-f", str(i + 1), "-l", str(i + 1), str(pdf), "-"],
                             capture_output=True, text=True)
        text.append(res.stdout)
    weak_word = "Kategoriye göre" if lang == "tr" else "Weaknesses by category"
    card_word = "NE YAPMIŞ?" if lang == "tr" else "WHAT DID IT DO?"
    fig_word = "Şekil 4." if lang == "tr" else "Figure 4."
    pick = [0,
            next(i for i, s_ in enumerate(text) if fig_word in s_),
            next(i for i, s_ in enumerate(text) if weak_word in s_),
            next(i for i, s_ in enumerate(text) if card_word in s_ and i > 2)]
    imgs = [Image.open(pages[i]).convert("RGB") for i in pick]
    pw_, ph_ = imgs[0].size
    scale = 330 / pw_
    imgs = [im.resize((330, int(ph_ * scale)), Image.LANCZOS) for im in imgs]
    pw_, ph_ = imgs[0].size
    margin, gap, label_h = 24, 28, 50
    W = margin * 2 + 4 * pw_ + 3 * gap
    H = margin * 2 + ph_ + label_h
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for k in range(4):
        x = margin + k * (pw_ + gap)
        sd.rectangle([x + 3, margin + 5, x + pw_ + 3, margin + ph_ + 5], fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    canvas.alpha_composite(shadow)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for k, im in enumerate(imgs):
        x = margin + k * (pw_ + gap)
        canvas.paste(im, (x, margin))
        draw.rectangle([x, margin, x + pw_ - 1, margin + ph_ - 1], outline=(208, 215, 222, 255))
        label = f"{k + 1}  {PREVIEW[lang]['labels'][k]}"
        tw = draw.textlength(label, font=font)
        draw.rounded_rectangle([x + pw_ / 2 - tw / 2 - 14, margin + ph_ + 12, x + pw_ / 2 + tw / 2 + 14,
                                margin + ph_ + 44], radius=16, fill=(31, 59, 87, 240))
        draw.text((x + pw_ / 2 - tw / 2, margin + ph_ + 16), label, font=font, fill=(255, 255, 255, 255))
    out = OUT / f"fig5-report-preview-{lang}.png"
    canvas.save(out, optimize=True)
    shutil.rmtree(work, ignore_errors=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="also build the report preview PNG (Figure 5)")
    ap.add_argument("--lang", default="en", help="comma-separated figure languages: en, tr (default: en)")
    a = ap.parse_args(argv)
    langs = [x.strip() for x in a.lang.split(",") if x.strip() in L]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in FIGURES.items():
        for lang in langs:
            for theme in ("light", "dark"):
                path = OUT / f"{name}-{lang}-{theme}.svg"
                path.write_text(fn(lang, theme), encoding="utf-8")
                print(f"wrote {path.relative_to(ROOT)}")
    if a.preview:
        for lang in langs:
            print(f"wrote {build_preview(lang).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
