"""Macao SAR -- MUST (Macau University of Science and Technology) tuition
fee schedule for Macao residents, snapshot.

MUST publishes a "先修班及學士學位課程學費表" (Foundation Year and Bachelor's
Degree Tuition Fee Table) PDF, linked from
https://www.must.edu.mo/file/tuition-fee.html -- verified live 2026-09-06:
200, 407KB, 2 pages, genuinely text-based (pdfplumber recovers clean text,
not scanned). Page 1 is a one-line-per-program table:
    <programme name> <duration>年制 $<annual fee> $<total fee>
for programmes with a UNIFORM per-year fee across their whole duration.
This fetcher matches exactly that shape via regex (duration marker
"<digit>年制" followed by two "$"-prefixed MOP amounts on the same line) --
27 of the ~33 listed programmes fit it cleanly (the foundation-year
programme at 1-year, plus 26 four-year bachelor's programmes).

Six programmes are intentionally NOT captured: Traditional Chinese
Medicine (5-year, tiered fee: $45,000/yr for years 1-4 then $38,000 for
year 5), Clinical Medicine (6-year, $85,000/yr years 1-5, year-6 fee set
per placement hospital -- genuinely unlisted), Pharmacy (5-year, tiered
$50,400/yr then $36,000), and their combined/derived rows -- these span
multiple PDF text lines with irregular structure that the single-line
regex correctly does not match, rather than silently mis-parsing them.
Recorded as a known gap, not a bug.

Only the Macao-residents fee schedule is fetched (the PDF has a separate
"non-Macao residents" sibling document, linked as its own PDF on the same
page, with different -- typically higher -- rates; not fetched here to
keep this source narrowly scoped to one schedule per run).

Effective date is read from the PDF's own Chinese-format footer line
("<YYYY>年<M>月<D>日生效" = "effective from YYYY-MM-DD").

Currency: MOP ("澳門幣" = Macau Pataca), matches countries.yaml.
coicop_classification: source_curated -- COICOP 10.4.0.0 (tertiary
education), single narrow class for the whole schedule.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.must.edu.mo/file/tuition-fee.html?locale=zh_MO"
_PDF_URL = "https://www.must.edu.mo/images/Admission/files/PreUBachelorFT_Macao_residents.pdf"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_must_tuition_fees"
_COICOP_CODE = "10.4.0.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_ROW_RE = re.compile(r"^(.+?)\s+[一二三四五六七八九十]+年制\s+\$([\d,]+)\s+\$([\d,]+)$", re.M)
_EFFECTIVE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日生效")


def fetch_mo_must_tuition_fees(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        pdf_resp = session.get(_PDF_URL, timeout=90)
        pdf_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed: %s", _SOURCE_KEY, exc)
        return None

    import pdfplumber

    try:
        with pdfplumber.open(BytesIO(pdf_resp.content)) as pdf:
            text = pdf.pages[0].extract_text() or ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF parse failed: %s", _SOURCE_KEY, exc)
        return None

    eff_m = _EFFECTIVE_RE.search(text)
    if eff_m:
        yyyy, mm, dd = (int(g) for g in eff_m.groups())
        effective_from = date(yyyy, mm, dd)
    else:
        effective_from = date.today()

    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    parsed: list[dict] = []
    for name, annual_raw, _total_raw in _ROW_RE.findall(text):
        name = name.strip()
        # strip a leading "N. " list-number prefix, present on the first
        # row of each section ("1. 大學先修班課程")
        name = re.sub(r"^\d+\.\s*", "", name)
        try:
            annual_fee = float(annual_raw.replace(",", ""))
        except ValueError:
            continue
        if annual_fee <= 0 or not name:
            continue
        parsed.append({"item_name": name[:200], "price_local": annual_fee})

    if not parsed:
        logger.warning("[%s] no fee rows parsed from %s", _SOURCE_KEY, _PDF_URL)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": "year",
            "source_url": _PDF_URL,
            "notes": "MUST tuition, Macao residents, per-year fee for uniform-rate programmes only",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
