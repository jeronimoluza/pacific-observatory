"""American Samoa Dept of Commerce (doc.as.gov), Statistics Division --
Consumer Price Index (CPI), quarterly, Modified-Laspeyres, base year 2007
(the newsletter text says "rebase in 2007").

Same doc.as.gov Wix FAQ widget as `doc_bfi.py` (see that module's docstring
for the full verified request sequence and `_wix_faq.py` for the shared
client) -- here filtered to the "Consumer Price Index" category. Each yearly
question entry embeds TWO link types per quarter: a "... CPI Press Release"
(short release, verified image-only/scanned in every sample checked --
skipped, no text to extract) and a "CPI Newsletter - <Quarter> <Year>" (the
full release, verified text-native for every quarter checked 2021 Q3
onward). Only Newsletter links are used; Press-Release-only quarters
(2019-2020, most of 2021) are skipped for lack of an extractable source.

Each Newsletter's first page carries a 10-group index table (current
quarter + prior quarter + year-ago quarter, plus % changes) -- only the
current quarter's column is kept. Groups map to COICOP-2018 divisions
below; "Education and Communications" is a genuinely combined column (no
single division covers both, same issue as the CNMI and Tuvalu CPI
fetchers' own combined labels) and is dropped; "All Items" is the headline
row, dropped pending a sanctioned all-items sentinel (see the onboarding
skill's open design questions).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
coicop_classification: publisher_labeled (static _COICOP_MAP below).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.eap.pacific_islands.american_samoa import _wix_faq
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "American Samoa"
_SOURCE_KEY = "as_doc_cpi"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "2007=100"

_CPI_CATEGORY_TITLE = "Consumer Price Index"
_CPI_CATEGORY_ID_FALLBACK = "5e921803-3d73-4dd3-a41e-81aa1413e9c4"

_QUARTERS = {"1st": 1, "2nd": 4, "3rd": 7, "3th": 7, "4th": 10}
_LABEL_QTR_RE = re.compile(
    r"(?P<q>1st|2nd|3rd|3th|4th)\s+Quarter\D*?(?P<year>\d{4})", re.IGNORECASE
)

_COICOP_MAP = {
    "food": "01",
    "alcoholicbeverages": "02",
    "housing": "04",
    "apparel": "03",
    "transportation": "07",
    "medicalcare": "06",
    "entertainment": "09",
    "othergoodsandservices": "12",
}
_DROP_KEYS = {"allitems", "educationandcommunications"}

_GROUP_ROW_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z .()&/'\-]*?)\s+"
    r"(?P<v1>-?\d+\.\d+)\s+(?P<v2>-?\d+\.\d+)\s+(?P<v3>-?\d+\.\d+)"
    r"(?:\s+-?\d+\.\d+){0,2}\s*$"
)


def _norm_key(label: str) -> str:
    return re.sub(r"[^a-z]", "", label.lower())


def _match_group(label: str) -> str | None:
    key = _norm_key(label)
    if not key:
        return None
    for candidate in list(_COICOP_MAP) + list(_DROP_KEYS):
        if candidate in key or key in candidate:
            return candidate
    return None


def _parse_newsletter_current_quarter(
    pdf_bytes: bytes, obs_date: date, pdf_url: str
) -> list[dict]:
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # The group index table lives on page 1 (0-indexed page 0).
        text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
    if not text.strip():
        return []

    ts = get_scrape_ts()
    rows: list[dict] = []
    for line in text.splitlines():
        m = _GROUP_ROW_RE.match(line.strip())
        if not m:
            continue
        group_key = _match_group(m.group("label"))
        if group_key is None:
            continue
        if group_key in _DROP_KEYS:
            logger.debug(
                "[%s] dropping %r (headline or combined column, no single COICOP division)",
                _SOURCE_KEY,
                m.group("label"),
            )
            continue
        coicop = _COICOP_MAP[group_key]
        try:
            index_value = float(m.group("v1"))  # leftmost = current quarter
        except ValueError:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": round(index_value, 4),
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "notes": f"category={m.group('label').strip()}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_as_doc_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )

    token = _wix_faq.get_faq_token(session, _SOURCE_KEY)
    if not token:
        return None
    category_id = _wix_faq.get_category_id(
        session, token, _CPI_CATEGORY_TITLE, _CPI_CATEGORY_ID_FALLBACK, _SOURCE_KEY
    )
    year_entries = _wix_faq.query_year_entries(session, token, category_id, _SOURCE_KEY)
    if not year_entries:
        logger.warning("[%s] no CPI year entries found", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    skipped = 0
    for entry in year_entries:
        links = _wix_faq.extract_links(entry.get("draftjs", ""))
        for label, url in links:
            if "newsletter" not in label.lower():
                continue  # Press Release links verified image-only, skip.
            m = _LABEL_QTR_RE.search(label)
            if not m:
                continue
            month_num = _QUARTERS[m.group("q").lower()]
            year = int(m.group("year"))
            obs_date = date(year, month_num, 1)
            if obs_date <= cutoff:
                continue
            pdf_url = _wix_faq.gdrive_direct(url)
            try:
                resp = session.get(pdf_url, timeout=60)
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] PDF fetch failed for %s: %s", _SOURCE_KEY, pdf_url, exc
                )
                continue
            q_rows = _parse_newsletter_current_quarter(resp.content, obs_date, pdf_url)
            if not q_rows:
                skipped += 1
                logger.info(
                    "[%s] %s: no extractable group table — skipped", _SOURCE_KEY, label
                )
                continue
            rows.extend(q_rows)

    if skipped:
        logger.info(
            "[%s] %d newsletter(s) skipped (no extractable table)", _SOURCE_KEY, skipped
        )
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
