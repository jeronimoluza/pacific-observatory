"""Libya Bureau of Statistics and Census (bsc.ly) -- monthly Consumer Price Index.

The "Prices and Price Index" section (`_LISTING_URL`) lists PDF releases titled
"Report on Inflation and Consumer Price Indices by Main Groups ... for <Month>
<Year> compared with <Month> <Year-1>". Verified live 2026-09-01: monthly PDFs run
from 2010 through July 2026 (uploaded 2026/08) -- genuinely current, not a stale
archive. Base year 2024=100.

Filenames are NOT a reliable naming convention (typos, "_compressed", "-1"/"-1-1"
suffixes, one .docx.pdf) so this fetcher does not guess a URL pattern the way the
Tunisia INS fetcher does. Instead it ranks every PDF link on the listing page by
its WordPress upload path (`/uploads/<year>/<month>/`, a reliable upper bound on
publish date) and opens the most recent candidates until one parses.

Each report PDF carries a genuine text-extractable table (pdfplumber
`extract_words()`, no OCR needed) headed "Main Groups | Code" with columns
[M-o-M %, <current-month> index, <year-ago-month> index, Weight] per group, plus a
bilingual English/Arabic label and Libya's own 2-digit group code:

  00 General Index                         -> headline, dropped (no IndexObservation
                                               sentinel for all-items -- see skill's
                                               "Open design questions")
  01 food and Beverages                    -> 01
  02 Tobacco                               -> 02
  03 clothing and Footwear                 -> 03
  04 Housing,Water,Electricity,Other fuel  -> 04
  05 Furniture and Household Equipment     -> 05
  06 Health                                -> 06
  07 Transport                             -> 07
  08 Communication                         -> 08
  09 Recreation and Culture                -> 09
  10 Education                             -> 10
  11 Restaurant and Hotels                 -> 11
  12 Miscellaneous goods and Services      -> 12

Libya's own classification is the pre-2018-revision 12-division scheme (like
Jordan's DOS CPI in this same shard) -- division 12 folds personal care/misc
without a separate division 13, so codes are used as published (identity mapping,
no translation table needed): "01"->"01" ... "12"->"12".

Only the current-period index column is emitted (period_kind=monthly_avg); the
year-ago comparator column in the same table is redundant with a prior month's own
row and is dropped rather than double-counted.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled (source's own 2-digit group code).
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://bsc.ly/economic_statistic/prices/"
_COUNTRY = "Libya"
_SOURCE_KEY = "ly_bsc_cpi"
_BASE_PERIOD = "2024=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_MAX_CANDIDATES = 8

_PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
_UPLOAD_PATH_RE = re.compile(r"/uploads/(\d{4})/(\d{2})/")
_PERIOD_RE = re.compile(r"for\s+([A-Za-z]+)\s+(\d{4})\s+compared\s+with", re.IGNORECASE)
_FLOAT_RE = re.compile(r"^\d{1,4}\.\d{1,2}$")
_CODE_RE = re.compile(r"^(0[0-9]|1[0-2])$")

_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _candidate_pdf_urls(html: str, base_url: str) -> list[str]:
    from urllib.parse import urljoin

    hrefs = set(_PDF_HREF_RE.findall(html))
    ranked = []
    for href in hrefs:
        m = _UPLOAD_PATH_RE.search(href)
        key = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        ranked.append((key, urljoin(base_url, href)))
    ranked.sort(key=lambda t: t[0], reverse=True)
    return [u for _, u in ranked[:_MAX_CANDIDATES]]


def _extract_report_period(pdf: "pdfplumber.PDF") -> tuple[int, int] | None:
    for page in pdf.pages[:2]:
        text = page.extract_text() or ""
        m = _PERIOD_RE.search(text)
        if m:
            month_name, year = m.group(1).lower(), int(m.group(2))
            month = _MONTH_NUM.get(month_name)
            if month:
                return year, month
    return None


def _extract_group_rows(pdf: "pdfplumber.PDF") -> list[dict] | None:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "General Index" not in text and "Main Groups" not in text:
            continue
        words = page.extract_words(x_tolerance=8, y_tolerance=3)
        from collections import defaultdict

        rows = defaultdict(list)
        for w in words:
            rows[round(w["top"], -1)].append(w)

        out = []
        for key in sorted(rows.keys()):
            tokens = [w["text"] for w in sorted(rows[key], key=lambda w: w["x0"])]
            floats_idx = [i for i, t in enumerate(tokens) if _FLOAT_RE.match(t)]
            if len(floats_idx) < 4:
                continue
            floats = [float(tokens[i]) for i in floats_idx[:4]]
            code_candidates = [t for t in tokens if _CODE_RE.match(t)]
            if not code_candidates:
                continue
            code = code_candidates[-1]
            out.append(
                {
                    "code": code,
                    "pct_change": floats[0],
                    "current_index": floats[1],
                    "prior_index": floats[2],
                    "weight": floats[3],
                }
            )
        if out:
            return out
    return None


def _rows_from_pdf(pdf_bytes: bytes, url: str, cutoff: date) -> list[dict] | None:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        period = _extract_report_period(pdf)
        if not period:
            return None
        year, month = period
        groups = _extract_group_rows(pdf)
        if not groups:
            return None

    obs_date = date(year, month, 1)
    if obs_date <= cutoff:
        return []

    ts_scrape = get_scrape_ts()
    out: list[dict] = []
    for g in groups:
        if g["code"] == "00":
            continue  # headline all-items -- no IndexObservation sentinel
        r = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": g["code"],
            "index_value": round(g["current_index"], 4),
            "index_base_period": _BASE_PERIOD,
            "source_url": url,
            "notes": f"weight={g['weight']}, mom_pct_change={g['pct_change']}",
            "scrape_ts": ts_scrape,
            "observation_hash": None,
        }
        r["observation_hash"] = make_hash(r, _IDENT)
        out.append(r)
    return out


def fetch_ly_bsc_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_LISTING_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] listing page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    for pdf_url in _candidate_pdf_urls(resp.text, _LISTING_URL):
        try:
            pdf_resp = session.get(pdf_url, timeout=60)
            pdf_resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s] pdf fetch failed %s: %s", _SOURCE_KEY, pdf_url, exc)
            continue
        try:
            rows = _rows_from_pdf(pdf_resp.content, pdf_url, cutoff)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s] pdf parse failed %s: %s", _SOURCE_KEY, pdf_url, exc)
            continue
        if rows is None:
            continue
        logger.info(
            "[%s] %d rows from %s (cutoff=%s)", _SOURCE_KEY, len(rows), pdf_url, cutoff
        )
        return pd.DataFrame(rows) if rows else None

    logger.warning("[%s] no parseable CPI report found among candidates", _SOURCE_KEY)
    return None
