"""Shared helpers for the econ-finance-lit-review scripts (standard library only)."""

from __future__ import annotations

import csv
import datetime as dt
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Working-folder layout. Stage number = file prefix. Keep in sync with
# references/templates.md and SKILL.md §3.
# ---------------------------------------------------------------------------
FILES = {
    "protocol": "00_protocol.md",
    "evidence_scan": "01_evidence_scan.md",
    "seeds": "01_seeds.csv",
    "search_log": "02_search_log.csv",
    "records": "03_records.csv",
    "records_dedup": "03_records_dedup.csv",
    "duplicates": "03_duplicates.csv",
    "screening": "04_screening.csv",
    "rescreen": "04_rescreen.csv",
    "prisma_counts": "04_prisma_counts.json",
    "verification": "05_verification.csv",
    "extraction": "06_extraction.csv",
    "estimates": "06_estimates.csv",
    "fulltext": "06_fulltext.csv",
    "cards": "06_study_cards.csv",
    "weaknesses": "06_weaknesses.csv",
    "appraisal": "07_appraisal.csv",
    "synthesis": "08_synthesis.md",
    "meta_dir": "08_meta",
    "gaps": "09_gaps.md",
    "figures_dir": "10_figures",
    "report_md": "10_report.md",
    "qa_log": "10_qa_log.md",
}

HEADERS = {
    FILES["seeds"]: ["seed_id", "title", "authors", "year", "doi", "role", "found_by"],
    FILES["search_log"]: [
        "query_id", "date", "source", "query_string", "filters", "hits", "retrieved", "notes",
    ],
    FILES["records"]: [
        "record_id", "source", "query_id", "title", "authors", "year", "venue", "volume",
        "issue", "pages", "doi", "url", "type", "language", "abstract", "notes",
    ],
    FILES["screening"]: ["record_id", "stage", "decision", "reason_code", "note"],
    FILES["verification"]: [
        "ref_id", "record_id", "status", "confidence", "method", "link", "link_check_method",
        "checked_on", "authors", "year", "title", "venue", "volume", "issue", "pages", "doi",
        "type", "series", "number", "publisher", "language", "retracted",
        "published_version_doi", "online_year", "evidence_level", "discrepancy_note",
    ],
    FILES["extraction"]: [
        "ref_id", "theme", "country_region", "sample_period", "frequency", "unit", "data_source",
        "method_family", "identification", "outcome", "key_regressors", "direction",
        "magnitude_units", "uncertainty", "location", "heterogeneity", "robustness",
        "limitations", "evidence_level", "notes",
    ],
    FILES["estimates"]: [
        "est_id", "ref_id", "estimate", "se", "t", "df", "effect_type", "outcome",
        "unit", "horizon", "sample", "location", "include", "notes",
    ],
    FILES["fulltext"]: [
        "ref_id", "doi", "oa_url", "oa_source", "version", "license", "checked_on", "notes",
    ],
    FILES["cards"]: [
        "ref_id", "theme", "pass1_abstract_conclusion", "pass2_intro_method", "pass3_literature",
        "what_it_did", "what_it_left_out", "relevance", "full_text_source", "evidence_level",
        "card_status", "notes",
    ],
    FILES["weaknesses"]: [
        "ref_id", "category", "severity", "weakness", "evidence_location", "basis", "notes",
    ],
    FILES["appraisal"]: [
        "ref_id", "identification", "data", "inference", "robustness", "transparency",
        "relevance", "total", "venue_info", "venue_source", "venue_checked_on", "notes",
    ],
}

# Weakness taxonomy for 06_weaknesses.csv (see references/study-cards.md)
WEAKNESS_CATEGORIES = [
    "question_contribution", "theory_specification", "identification", "data_measurement",
    "estimation_inference", "robustness", "external_validity", "literature_positioning",
    "transparency_replication", "policy_interpretation",
]
WEAKNESS_LABELS = {
    "en": {
        "question_contribution": "Question & contribution", "theory_specification": "Theory & specification",
        "identification": "Identification", "data_measurement": "Data & measurement",
        "estimation_inference": "Estimation & inference", "robustness": "Robustness",
        "external_validity": "External validity", "literature_positioning": "Literature positioning",
        "transparency_replication": "Transparency & replication", "policy_interpretation": "Policy interpretation",
    },
    "tr": {
        "question_contribution": "Soru ve katkı", "theory_specification": "Teori ve model kurgusu",
        "identification": "Tanımlama (nedensellik)", "data_measurement": "Veri ve ölçüm",
        "estimation_inference": "Tahmin ve çıkarım", "robustness": "Sağlamlık",
        "external_validity": "Dış geçerlilik", "literature_positioning": "Literatürdeki konumlanma",
        "transparency_replication": "Şeffaflık ve tekrarlanabilirlik", "policy_interpretation": "Politika yorumu",
    },
}
SEVERITIES = ["high", "medium", "low"]
WEAKNESS_BASES = ["author-stated", "reviewer-identified"]

PRINTABLE_STATUSES = {"VERIFIED", "PARTIAL", "PREPRINT"}
BLOCKED_STATUSES = {"NOT_VERIFIED", "RETRACTED"}
WP_TYPES = {"working-paper", "preprint", "report"}
OTHER_METHOD_PREFIXES = ("snowball", "citation", "author", "seed", "user", "website", "manual",
                         "prior-review", "other")

PARTICLES = {"de", "da", "del", "der", "di", "du", "van", "von", "le", "la", "dos", "das", "ter", "ten"}

_FOLD_MAP = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
                           "ç": "c", "Ç": "C", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U",
                           "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "æ": "ae", "œ": "oe",
                           "ß": "ss", "đ": "d", "Đ": "D"})


def strip_accents(text: str) -> str:
    text = (text or "").translate(_FOLD_MAP)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def norm_text(text: str) -> str:
    """Lowercase, accent-free, punctuation-free, single-spaced."""
    text = strip_accents(text).casefold()
    text = re.sub(r"<[^>]+>", " ", text)          # stray markup from APIs
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_title(title: str, drop_subtitle: bool = False) -> str:
    title = title or ""
    if drop_subtitle:
        title = re.split(r"[:?!]\s", title, maxsplit=1)[0]
    return norm_text(title)


def title_similarity(a: str, b: str) -> float:
    """Best of full-title and main-title similarity (subtitles often differ)."""
    if not norm_title(a) or not norm_title(b):
        return 0.0
    full = SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()
    main = SequenceMatcher(None, norm_title(a, True), norm_title(b, True)).ratio()
    return max(full, main)


def norm_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    return doi.strip().rstrip(".").lower()


def split_authors(authors: str) -> list[str]:
    """Authors are stored as 'Family, Given; Family, Given'."""
    return [a.strip() for a in (authors or "").split(";") if a.strip()]


def family_name(author: str) -> str:
    return author.split(",", 1)[0].strip()


def given_name(author: str) -> str:
    parts = author.split(",", 1)
    return parts[1].strip() if len(parts) > 1 else ""


def norm_surname(name: str) -> str:
    tokens = norm_text(name).split()
    core = [t for t in tokens if t not in PARTICLES]
    return " ".join(core or tokens)


def surname_match(a: str, b: str) -> bool:
    na, nb = norm_surname(a), norm_surname(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # compound surnames: 'garcia' vs 'garcia lopez', 'klingeberg' vs 'geyer klingeberg'
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta & tb) and (ta <= tb or tb <= ta)


def first_author_family(authors: str) -> str:
    names = split_authors(authors)
    return family_name(names[0]) if names else ""


def to_int(value) -> int | None:
    m = re.search(r"(1[89]\d{2}|20\d{2})", str(value or ""))
    return int(m.group(1)) if m else None


def is_other_method(source: str) -> bool:
    """True for records found outside database searching (PRISMA 'other methods')."""
    return (source or "").strip().lower().startswith(OTHER_METHOD_PREFIXES)


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip(): (v if v is not None else "") for k, v in row.items()}
                for row in csv.DictReader(fh)]


def write_csv(path: str | Path, rows: list[dict], header: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in header})


def slugify(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", strip_accents(text).lower()).strip("-")
    return slug[:max_len].rstrip("-") or "review"


def find_record(rows: list[dict], title: str = "", doi: str = "", authors: str = "",
                year=None, threshold: float = 0.90) -> dict | None:
    """Locate a record by DOI, else by title similarity (+ first author / year when given)."""
    d = norm_doi(doi)
    if d:
        for r in rows:
            if norm_doi(r.get("doi", "")) == d:
                return r
    if not title:
        return None
    fa, y = first_author_family(authors), to_int(year)
    best, best_sim = None, 0.0
    for r in rows:
        sim = title_similarity(title, r.get("title", ""))
        if sim < threshold:
            continue
        fr = first_author_family(r.get("authors", ""))
        if fa and fr and not surname_match(fa, fr):
            continue
        yr = to_int(r.get("year"))
        if y and yr and abs(y - yr) > 2:
            continue
        if sim > best_sim:
            best, best_sim = r, sim
    return best


# ---------------------------------------------------------------------------
# Time window and environment helpers
# ---------------------------------------------------------------------------
DEFAULT_WINDOW_YEARS = 5


def default_window(today: dt.date | None = None, years: int = DEFAULT_WINDOW_YEARS) -> tuple[int, int]:
    """Default literature window: publication years [Y - years, Y] for the current year Y."""
    today = today or dt.date.today()
    return today.year - years, today.year


def parse_window(text: str | None, today: dt.date | None = None) -> tuple[int, int]:
    """Parse '2020-2026', '2020-present', '2020–günümüz', '2020', 'since 2019', '2019'dan beri',
    'last 10 years' or 'son 10 yıl'; None/'' gives the default (last five years)."""
    if not text or not str(text).strip():
        return default_window(today)
    today = today or dt.date.today()
    t = str(text).strip().lower().replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    t = re.sub(r"\s+", "", t)
    last = re.fullmatch(r"(?:last|past|son)(\d{1,2})(?:years?|y[iı]l)", t)
    if last:
        return today.year - int(last.group(1)), today.year
    since = re.fullmatch(r"(?:since|from)(\d{4})|(\d{4})(?:'?(?:dan|den|tan|ten))?(?:beri|itibaren|sonras[iı]|onwards?)", t)
    if since:
        start = int(since.group(1) or since.group(2))
        if start > today.year:
            raise ValueError(f"window start {start} is in the future")
        return start, today.year
    m = re.fullmatch(r"(\d{4})(?:-(\d{4}|present|now|today|g[uü]n[uü]m[uü]z|bug[uü]n))?", t)
    if not m:
        raise ValueError(f"cannot parse window {text!r}; use e.g. 2021-2026 or 2021-present")
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else today.year
    if not m.group(2):
        end = start
    if end < start:
        raise ValueError(f"window end {end} is before start {start}")
    return start, end


def window_from_protocol(folder: Path) -> tuple[int, int] | None:
    """Read 'Literature window: 2021-2026' (or 'Literatür penceresi: ...') from 00_protocol.md."""
    path = Path(folder) / FILES["protocol"]
    if not path.exists():
        return None
    m = re.search(r"(?:Literature window|Literatür penceresi)\s*:\s*(\d{4})\s*[-\u2013]\s*(\d{4})",
                  path.read_text(encoding="utf-8"))
    return (int(m.group(1)), int(m.group(2))) if m else None


def in_window(year, window: tuple[int, int]) -> bool | None:
    """True/False when the year is known, None when it cannot be read."""
    y = to_int(year)
    if y is None:
        return None
    return window[0] <= y <= window[1]


def load_env(path: str | Path | None = None) -> dict:
    """Merge KEY=VALUE lines from an optional .env file into a copy of os.environ (values never printed)."""
    env = dict(os.environ)
    p = Path(path) if path else Path(".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Turn an OpenAlex abstract_inverted_index into plain text."""
    if not inverted_index:
        return ""
    positions = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    return " ".join(w for _, w in sorted(positions))


def strip_markup(text: str) -> str:
    """Remove JATS/HTML tags (Crossref abstracts) and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()
