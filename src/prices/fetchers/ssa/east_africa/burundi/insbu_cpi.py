"""INSBU (Institut National de la Statistique du Burundi, formerly known
as ISTEEBU under its old name) -- monthly national CPI ("Indice des Prix
à la Consommation des ménages au Burundi") bulletin PDF.

Note on the country's old acronym: the domain isteebu.bi (named in the
onboarding brief) has been squatted by an unrelated SEO reseller ("Nova
Network") -- it is NOT the statistics office and returns no INSBU
content. The live institute is at insbu.bi / api.insbu.bi; discovered via
the Knoema-hosted "Burundi Data Portal" (burundi.opendataforafrica.org),
whose "consumer-price-index-national" dataset metadata carries
`"ref": "https://www.insbu.bi/"`. INSBU's own site (insbu.bi) is a React
SPA; its JS bundle names the backing API at `api.insbu.bi/api/publications`.

`GET https://api.insbu.bi/api/publications?per_page=200&page=N` returns a
mixed feed of all INSBU publication types (CPI, construction-cost index,
etc), paginated (`meta.last_page`, ~50/page). Only
`type_publication == "ipc_fr"` (the French-language monthly CPI bulletin;
"ipc_ki" is the same content in Kirundi) is used here. This fetcher only
walks the FIRST page (most recent ~50 publications, comfortably >12
months of monthly cadence) rather than the full ~499-publication /
10-page history, since each bulletin's own national table already
carries 3 monthly columns (see below) -- deeper backfill would need
per-release PDF parsing at 10x the cost for diminishing new months.

Each monthly PDF's national-level table (the one headed "Rubriques" /
"TOUS LES PRODUITS", found by searching page text for "Rubriques") gives
3 index columns: same month one year ago, prior month, and the current
month (title-derived) -- e.g. for the August 2026 release: août-25,
juil.-26, août-26. Column dates are derived by month-arithmetic from the
bulletin's own title ("Mois d'août 2026" -> current = 2026-08-01, prior =
2026-07-01, year-ago = 2025-08-01) rather than parsed from the table's
own (line-wrapped, abbreviation-inconsistent) column headers.

12 COICOP-2018-style divisions (bare-integer row codes 1-12; "0" is the
all-items headline, dropped -- no sanctioned all-items COICOP sentinel
yet). Row-matching requires the leading token to be a BARE 1-2 digit
integer with no decimal point, to avoid matching the same table's
sub-group/class rows ("01.1", "01.1.1", etc, which use the same digits
with a "." and are not divisions).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
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

_PUBLICATIONS_URL = "https://api.insbu.bi/api/publications"
_COUNTRY = "Burundi"
_SOURCE_KEY = "bi_insbu_cpi"
_INDEX_BASE_PERIOD = "2016/2017=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_DIVISION_LABELS = {
    "1": "Produits alimentaires et boissons non alcoolisées",
    "2": "Boissons alcoolisées et tabac",
    "3": "Articles d'habillement et chaussures",
    "4": "Logement, eau, gaz, électricité et autres combustibles",
    "5": "Meubles, articles de ménage et entretien courant du foyer",
    "6": "Santé",
    "7": "Transports",
    "8": "Communications",
    "9": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restaurants et hôtels",
    "12": "Biens et services divers",
}
_DIVISION_CODES = {k: (f"0{k}" if len(k) == 1 else k) for k in _DIVISION_LABELS}

_MONTH_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_TITLE_MONTH_RE = re.compile(
    r"mois\s+d[’']\s*(" + "|".join(_MONTH_FR) + r")\s+(\d{4})", re.IGNORECASE
)

# Bare 1-2 digit division code (no decimal point) at line start, followed
# by a label, a weight, then 3 index values and 3 inflation figures --
# all French-locale decimals (comma, not dot).
_NUM = r"(-?[\d]+,[\d]+)"
_ROW_RE = re.compile(
    r"^(\d{1,2})\s+(.+?)\s+" + _NUM + r"\s+" + _NUM + r"\s+" + _NUM + r"\s+" + _NUM,
    re.MULTILINE,
)


def _fr_num(s: str) -> float:
    return float(s.replace(",", "."))


def _add_months(d: date, delta: int) -> date:
    month0 = d.month - 1 + delta
    year = d.year + month0 // 12
    month = month0 % 12 + 1
    return date(year, month, 1)


def _find_latest_ipc_fr(session: curl_requests.Session) -> dict | None:
    resp = session.get(
        _PUBLICATIONS_URL, params={"per_page": 200, "page": 1}, timeout=30, impersonate="chrome124"
    )
    resp.raise_for_status()
    pubs = resp.json().get("data", [])
    ipc_fr = [p for p in pubs if p.get("type_publication") == "ipc_fr"]
    if not ipc_fr:
        return None
    ipc_fr.sort(key=lambda p: p.get("date", ""), reverse=True)
    return ipc_fr[0]


def _extract_national_table(text: str) -> str | None:
    idx = text.find("Rubriques")
    if idx == -1:
        return None
    end = text.find("Autres Statistiques dérivées", idx)
    return text[idx: end if end != -1 else idx + 4000]


def fetch_bi_insbu_cpi(cutoff: date) -> pd.DataFrame | None:
    session = curl_requests.Session()

    pub = _find_latest_ipc_fr(session)
    if pub is None:
        logger.warning("[%s] No ipc_fr publication found", _SOURCE_KEY)
        return None

    title_match = _TITLE_MONTH_RE.search(pub.get("title", ""))
    if title_match is None:
        logger.warning("[%s] Could not parse month/year from title: %s", _SOURCE_KEY, pub.get("title"))
        return None
    month_name, year_str = title_match.groups()
    current_month = date(int(year_str), _MONTH_FR[month_name.lower()], 1)
    month_dates = [
        _add_months(current_month, -12),  # same month, prior year
        _add_months(current_month, -1),   # prior month
        current_month,                     # current month
    ]

    pdf_url = pub.get("document_url")
    if not pdf_url:
        logger.warning("[%s] Publication %s has no document_url", _SOURCE_KEY, pub.get("id"))
        return None

    resp = session.get(pdf_url, timeout=60, impersonate="chrome124")
    if resp.status_code != 200:
        logger.warning("[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, resp.status_code, pdf_url)
        return None

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    table_text = _extract_national_table(full_text)
    if table_text is None:
        logger.warning("[%s] Could not locate national COICOP table in %s", _SOURCE_KEY, pdf_url)
        return None

    rows: list[dict] = []
    for m in _ROW_RE.finditer(table_text):
        code_raw, label, _weight, idx1_str, idx2_str, idx3_str = m.groups()
        if code_raw not in _DIVISION_LABELS:
            continue  # "0" (all-items, no sentinel) or a stray non-division digit
        coicop = _DIVISION_CODES[code_raw]
        for month_date, idx_str in zip(month_dates, (idx1_str, idx2_str, idx3_str)):
            if month_date <= cutoff:
                continue
            row = {
                "observation_date": month_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": _fr_num(idx_str),
                "index_base_period": _INDEX_BASE_PERIOD,
                "source_url": pdf_url,
                "notes": _DIVISION_LABELS[code_raw],
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
