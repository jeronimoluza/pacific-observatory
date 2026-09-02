"""Statistics Sierra Leone (Stats SL) — Consumer Price Index press releases.

Stats SL publishes a monthly CPI press release PDF at statistics.sl. Each
release's "Table 3: National Consumer Price Index by Main COICOP Groups"
carries the FULL monthly index series back to the base period (December
2021=100), not just the current month — so a single, most-recent PDF is
enough to backfill the whole series in one fetch.

The live site 403s on a bare `requests` UA (confirmed) but is wide open with
any realistic browser User-Agent — no WAF, no TLS-fingerprint check, no
Cloudflare. Not a bot-block, just a naive UA-string gate.

Emits IndexObservation rows (analytical_role: cpi_benchmark).

Stats SL group -> COICOP-2018 division mapping (12 groups; division 13 is
absent from this publication, matching the same gap seen in other national
CPI series in this region):

  Food and Non-Alcoholic Beverages                              -> 01
  Alcoholic Beverages, Tobacco and Narcotics                     -> 02
  Clothing and Footwear                                          -> 03
  Housing, Water, Electricity, Gas and Other Fuels               -> 04
  Furnishings, household equipment and routine household
    maintenance                                                  -> 05
  Health                                                          -> 06
  Transport                                                       -> 07
  Communication                                                   -> 08
  Recreation and Culture                                          -> 09
  Education Services                                              -> 10
  Restaurant and Hotels                                           -> 11
  Miscellaneous Goods and Services                                -> 12

The "All Items" headline column is dropped (no sanctioned sentinel COICOP
code yet for an all-items row -- see the skill's open design question).

No currency involved (index values, not price levels) -- the SLE/SLL
redenomination trap does not apply to this source.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_LISTING_URL = "https://www.statistics.sl/index.php/cpi.html"
_COUNTRY = "Sierra Leone"
_SOURCE_KEY = "sl_statssl_cpi"
_BASE_PERIOD = "December 2021=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_COICOP_COLUMNS = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
]

_COICOP_LABELS = [
    "Food and Non-Alcoholic Beverages",
    "Alcoholic Beverages, Tobacco and Narcotics",
    "Clothing and Footwear",
    "Housing, Water, Electricity, Gas and Other Fuels",
    "Furnishings, household equipment and routine household maintenance",
    "Health",
    "Transport",
    "Communication",
    "Recreation and Culture",
    "Education Services",
    "Restaurant and Hotels",
    "Miscellaneous Goods and Services",
]

_MONTH_NUM = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# e.g. "July-2026-CPI_Press_Release.pdf", "cpi_press_release_for_august_2009.pdf",
# "stats_sl_cpi_for_september2019_press_release.pdf"
_PDF_MONTH_YEAR_RE = re.compile(
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"[\-_ ]*(\d{4})",
    re.IGNORECASE,
)

# Data rows in Table 3, e.g. "Jan-21 88.12 80.29 92.83 ... 86.89" (13 numbers:
# 12 divisions + All Items). A trailing page-footer digit sometimes leaks onto
# the same "line" after a newline the regex's \s+ swallows -- cap at 13 values.
_TABLE3_ROW_RE = re.compile(r"^([A-Za-z]+)[\-\s](\d{2})\s+([\d.\s]+)$", re.MULTILINE)


def _month_num_from_name(name: str) -> int | None:
    return _MONTH_NUM.get(name.lower())


def _list_pdf_urls(session: requests.Session) -> list[str]:
    resp = session.get(_LISTING_URL, timeout=30)
    resp.raise_for_status()
    hrefs = re.findall(r'href="([^"]+\.pdf[^"]*)"', resp.text, re.IGNORECASE)
    urls = []
    for h in hrefs:
        if "/cpi/" not in h.lower():
            continue
        if h.startswith("http"):
            urls.append(h)
        else:
            urls.append("https://www.statistics.sl" + h)
    return sorted(set(urls))


def _pick_latest_pdf(urls: list[str]) -> tuple[str, date] | None:
    best: tuple[str, date] | None = None
    for u in urls:
        m = _PDF_MONTH_YEAR_RE.search(u.rsplit("/", 1)[-1])
        if not m:
            continue
        month_num = _month_num_from_name(m.group(1))
        year = int(m.group(2))
        if month_num is None:
            continue
        d = date(year, month_num, 1)
        if best is None or d > best[1]:
            best = (u, d)
    return best


def _extract_table3(text: str) -> list[tuple[date, str, float]]:
    idx = text.find("Table 3")
    if idx == -1:
        return []
    table_text = text[idx:]

    results: list[tuple[date, str, float]] = []
    for m in _TABLE3_ROW_RE.finditer(table_text):
        mon_raw, yy, nums_str = m.groups()
        month_num = _month_num_from_name(mon_raw)
        if month_num is None:
            continue
        nums = re.findall(r"[\d]+\.?[\d]*", nums_str)
        if len(nums) < 13:
            continue
        nums = nums[:13]  # 12 divisions + All Items; drop any footer leakage
        year = 2000 + int(yy)
        obs_date = date(year, month_num, 1)
        for i, coicop in enumerate(_COICOP_COLUMNS):
            try:
                results.append((obs_date, coicop, float(nums[i])))
            except (IndexError, ValueError):
                pass
    return results


def fetch_sl_statssl_cpi(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    urls = _list_pdf_urls(session)
    if not urls:
        logger.warning("[%s] No CPI PDF links found on listing page", _SOURCE_KEY)
        return None

    picked = _pick_latest_pdf(urls)
    if picked is None:
        logger.warning("[%s] Could not parse a date from any PDF filename", _SOURCE_KEY)
        return None
    pdf_url, release_month = picked

    resp = session.get(pdf_url, timeout=60)
    if resp.status_code != 200:
        logger.warning(
            "[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, resp.status_code, pdf_url
        )
        return None

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    series = _extract_table3(text)
    if not series:
        logger.warning("[%s] No Table 3 rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    rows: list[dict] = []
    for obs_date, coicop, idx_val in series:
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "notes": _COICOP_LABELS[_COICOP_COLUMNS.index(coicop)],
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
