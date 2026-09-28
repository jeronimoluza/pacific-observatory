"""Institut National de la Statistique du Congo (INS) -- Indice National
Harmonise des Prix a la Consommation (INHPC), Republic of the Congo.

INS publishes one PDF bulletin per month. The production site
(ins-congo.cg) links to per-month HTML article pages with no reliable PDF
href; a mirror, site-ins-congo.vercel.app/stat-prix.html, lists every
bulletin PDF directly under one page -- that listing is used to find the
latest bulletin.

Each bulletin's "Tableau 1.1: Indice national harmonise des prix a la
consommation, base 100 : 2018" (national level, page ~6-7) carries one row
per COICOP function with a weight ("Pond.") and index levels for five
labelled comparison months (typically: same month last year, three recent
months, and the current month), followed by 1/3/12-month variation
percentages that this fetcher drops. Column months are parsed from the
table's own header row, not hardcoded, since which five months a bulletin
shows can shift.

Table extraction note: as with ins_cameroun_cpi.py, pdfplumber's word order
follows each visual TEXT LINE top-to-bottom, so a function label wrapping
onto two lines (e.g. "Logement, eau, electricite, gaz\net autres
combustibles") has its second line appear AFTER that row's numeric cells in
reading order. This fetcher matches on each label's first (unique) line
only, which always precedes its numbers.

INS's 12 "Fonctions" map 1:1 onto COICOP-2018 divisions 01-12 (division 13,
insurance/financial services, is absent -- the same gap as Cameroon, Sierra
Leone and most national CPI series in the region). The "INDICE GLOBAL"
headline row is dropped (no sanctioned sentinel COICOP code yet -- see the
skill's open design question).

No currency involved (index values, not price levels).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://site-ins-congo.vercel.app/stat-prix.html"
_LISTING_BASE = "https://site-ins-congo.vercel.app/"
_COUNTRY = "Congo, Rep."
_SOURCE_KEY = "cog_ins_congo_cpi"
_BASE_PERIOD = "Base 100 annee 2018"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_DIVISIONS = [
    ("01", "Produits alimentaires et"),
    ("02", "Boissons alcoolisées, tabac et"),
    ("03", "Articles d’habillement et"),
    ("04", "Logement, eau, électricité, gaz"),
    ("05", "Meubles, articles de ménages et"),
    ("06", "Santé"),
    ("07", "Transports"),
    ("08", "Communication"),
    ("09", "Loisirs et culture"),
    ("10", "Enseignement"),
    ("11", "Restaurants et hôtels"),
    ("12", "Biens et services divers"),
]
_LABELS_BY_CODE = {code: label for code, label in _DIVISIONS}

_MONTH_ABBR_FR = {
    "janv": 1, "janvier": 1, "fevr": 2, "févr": 2, "fev": 2,
    "fevrier": 2, "février": 2,
    "mars": 3, "avr": 4, "avril": 4,
    "mai": 5, "juin": 6, "juil": 7, "juillet": 7,
    "aout": 8, "août": 8,
    "sept": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "dec": 12, "déc": 12, "decembre": 12, "décembre": 12,
}

_MONTH_FILENAME_RE = re.compile(
    r"(janvier|janv|fevrier|f[ée]vrier|f[ée]vr|mars|avril|avr|mai|juin|"
    r"juillet|juil|aout|ao[uû]t|septembre|sept|octobre|oct|novembre|nov|"
    r"decembre|d[ée]cembre|dec)[-_ ]?(?<!\d)(\d{4})(?!\d)",
    re.IGNORECASE,
)

_HEADER_MONTH_RE = re.compile(r"([a-zéû]{3,9})[.\-](\d{2})\b", re.IGNORECASE)
_NUM_TOKEN_RE = re.compile(r"-?\d+,\d+%?")

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _get(url: str):
    return curl_requests.get(
        url, impersonate="firefox133", headers={"User-Agent": _UA}, timeout=60
    )


def _list_pdf_urls(html: str) -> list[str]:
    hrefs = re.findall(r'href="([^"]+\.pdf)"', html, re.IGNORECASE)
    out = []
    for h in hrefs:
        if h.startswith("http"):
            out.append(h)
        else:
            out.append(_LISTING_BASE + h.lstrip("/"))
    return sorted(set(out))


def _month_key(name: str) -> int | None:
    name = name.lower().rstrip(".")
    return _MONTH_ABBR_FR.get(name)


def _pick_latest_pdf(urls: list[str]) -> tuple[str, date] | None:
    best: tuple[str, date] | None = None
    for u in urls:
        for m in _MONTH_FILENAME_RE.finditer(u):
            month_num = _month_key(m.group(1))
            if month_num is None:
                continue
            year = int(m.group(2))
            d = date(year, month_num, 1)
            if best is None or d > best[1]:
                best = (u, d)
    return best


def _find_table_page(pdf) -> object | None:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Tableau 1. 1" in text and "INDICE GLOBAL" in text:
            return page
    return None


def _extract_header_months(text: str) -> list[date]:
    idx = text.find("Libellé")
    if idx == -1:
        idx = text.find("INDICE GLOBAL")
    header_region = text[max(0, idx - 200) : idx + 200] if idx != -1 else text[:400]
    months: list[date] = []
    for m in _HEADER_MONTH_RE.finditer(header_region):
        month_num = _month_key(m.group(1))
        if month_num is None:
            continue
        year = 2000 + int(m.group(2))
        months.append(date(year, month_num, 1))
        if len(months) == 5:
            break
    return months


def _extract_divisions(page) -> dict[str, list[float]]:
    words = page.extract_words()
    full_text = " ".join(w["text"] for w in words)
    # The prose paragraphs above the table name several functions by hand
    # (e.g. "... des fonctions « Logement, eau, électricité, gaz et autres
    # combustibles », « Transports » ainsi que « Produits alimentaires et
    # boissons non alcoolisées », qui ont enregistré ... 5,1 %, 4,3 % et
    # 2,1 %."), so a plain text.find(label) over the whole page can lock
    # onto a sentence's own percentages instead of the table row. Scope the
    # search to start at "INDICE GLOBAL" (all-caps, unique to the table
    # header row; prose uses lowercase "l'indice global").
    table_start = full_text.find("INDICE GLOBAL")
    text = full_text[table_start:] if table_start != -1 else full_text
    out: dict[str, list[float]] = {}
    for code, label in _DIVISIONS:
        idx = text.find(label)
        if idx == -1:
            logger.warning("[%s] label not found in Tableau 1.1: %r", _SOURCE_KEY, label)
            continue
        rest = text[idx + len(label) :]
        tokens = _NUM_TOKEN_RE.findall(rest)[:9]
        if len(tokens) < 6:
            logger.warning(
                "[%s] only %d numeric tokens after label %r (need >=6)",
                _SOURCE_KEY,
                len(tokens),
                label,
            )
            continue
        # tokens[0] = Pond. (weight), tokens[1:6] = the 5 monthly index levels
        index_values = [float(t.rstrip("%").replace(",", ".")) for t in tokens[1:6]]
        out[code] = index_values
    return out


def fetch_cog_ins_congo_cpi(cutoff: date) -> pd.DataFrame | None:
    resp = _get(_LISTING_URL)
    if resp.status_code != 200:
        logger.warning("[%s] listing fetch failed (%s)", _SOURCE_KEY, resp.status_code)
        return None

    urls = _list_pdf_urls(resp.text)
    if not urls:
        logger.warning("[%s] no bulletin PDFs found on listing page", _SOURCE_KEY)
        return None

    picked = _pick_latest_pdf(urls)
    if picked is None:
        logger.warning("[%s] could not parse month/year from any PDF url", _SOURCE_KEY)
        return None
    pdf_url, _ref_month = picked

    pdf_resp = _get(pdf_url)
    if pdf_resp.status_code != 200:
        logger.warning(
            "[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, pdf_resp.status_code, pdf_url
        )
        return None

    with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
        table_page = _find_table_page(pdf)
        if table_page is None:
            logger.warning("[%s] Tableau 1.1 page not found in %s", _SOURCE_KEY, pdf_url)
            return None
        page_text = table_page.extract_text() or ""
        months = _extract_header_months(page_text)
        divisions = _extract_divisions(table_page)

    if not divisions or len(months) != 5:
        logger.warning(
            "[%s] parse incomplete (%d divisions, %d header months)",
            _SOURCE_KEY,
            len(divisions),
            len(months),
        )
        return None

    rows: list[dict] = []
    for code, values in divisions.items():
        if len(values) != len(months):
            logger.warning(
                "[%s] division %s: %d values vs %d expected months, skipping",
                _SOURCE_KEY,
                code,
                len(values),
                len(months),
            )
            continue
        for obs_date, idx_val in zip(months, values):
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": idx_val,
                "index_base_period": _BASE_PERIOD,
                "source_url": pdf_url,
                "notes": _LABELS_BY_CODE[code],
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
