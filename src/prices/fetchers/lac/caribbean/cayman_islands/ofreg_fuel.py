"""OfReg (Utility Regulation and Competition Office, Cayman Islands) — weekly
retail fuel price survey.

OfReg publishes a "Retail Fuel Prices Report" PDF every Tuesday, linked from
a static listing page (ofreg.ky/fuel/retail-fuel-prices) under
/viewPDF/documents/<YYYY-MM-DD>-...-Reports<Weekday><DD><Month><YYYY>.pdf.
The fetcher re-discovers the latest link from the listing page each run
(filenames are not predictable beyond the embedded date) and takes the
newest by the date encoded in the URL.

The PDF's first page is a long per-station table (by brand: ESSO, Rubis,
Marinas, Independent) that is genuinely awkward to parse structurally (each
brand block repeats its own 3-row merged header, columns shift for the
Independent block which adds mid-grade/E85/bio-diesel columns). Page 2
carries the report's own pre-aggregated "Retail Network Average Weekly
Price Analysis" table — exactly 3 rows (Regular Gasoline, Premium Gasoline,
Diesel), each an already-averaged Cayman-wide price for the report week.
This fetcher reads that table rather than re-deriving the same average from
per-station rows itself — the publisher's own aggregation is the intended
official average, and re-averaging noisy per-brand table layouts would only
add a second place to introduce a bug.

Currency: KYD, stated explicitly and unambiguously in the report's own
text ("average retail fuel prices are provided in Cayman Islands dollars
per imperial gallon") — no inference from a bare "$" needed, unlike every
other source onboarded for this country this wave.

Emits PriceObservation rows (analytical_role: official_avg).
coicop_classification: source_curated (fuel retail -> 07.2.2, narrow).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pdfplumber
import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Cayman Islands"
_CURRENCY = "KYD"
_SOURCE_KEY = "ky_ofreg_fuel"
_UNIT = "imperial_gallon"
_LISTING_URL = "https://www.ofreg.ky/fuel/retail-fuel-prices"
_PDF_HREF_RE = re.compile(
    r'href="(https://www\.ofreg\.ky/viewPDF/documents/'
    r'(\d{4})-(\d{2})-(\d{2})-[^"]*\.pdf)"',
    re.IGNORECASE,
)
_REPORT_DATE_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(\d{1,2}\s+\w+\s+\d{4})"
)
_FUEL_ROW_RE = re.compile(
    r"^(Regular Gasoline|Premium Gasoline|Diesel)\b", re.IGNORECASE
)
_IDENT = ["source_key", "observation_date", "item_name"]


def _find_pdf_urls(session) -> list[str]:
    """All unique report URLs on the listing page, oldest first.

    The listing page repeats each link (once in a list view, once in a
    calendar widget) -- de-dup by URL. Only ~12 reports (roughly 3 months
    of weekly reports) are visible at a time, so this is a rolling window,
    not full history; a fetcher run only ever backfills what's currently
    listed.
    """
    try:
        resp = session.get(_LISTING_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] listing page fetch failed: %s", _SOURCE_KEY, exc)
        return []
    matches = _PDF_HREF_RE.findall(resp.text)
    seen: dict[str, tuple] = {}
    for full_url, yyyy, mm, dd in matches:
        seen[full_url] = (yyyy, mm, dd)
    return sorted(seen, key=lambda u: seen[u])


def _rows_from_pdf(pdf_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        m = _REPORT_DATE_RE.search(full_text)
        if not m:
            logger.warning("[%s] no report date found in PDF text", _SOURCE_KEY)
            return []
        try:
            obs_date = datetime.strptime(m.group(1), "%d %B %Y").date()
        except ValueError:
            logger.warning("[%s] unparseable report date %r", _SOURCE_KEY, m.group(1))
            return []
        if obs_date <= cutoff:
            return []

        avg_table = None
        for p in pdf.pages:
            for t in p.extract_tables():
                if (
                    t
                    and t[0]
                    and isinstance(t[0][0], str)
                    and ("Retail Network Average Weekly Price Analysis" in t[0][0])
                ):
                    avg_table = t
                    break
            if avg_table:
                break
    if avg_table is None:
        logger.warning("[%s] network-average table not found", _SOURCE_KEY)
        return []

    ts = get_scrape_ts()
    out: list[dict] = []
    for row in avg_table[1:]:
        if not row or not isinstance(row[0], str):
            continue
        m = _FUEL_ROW_RE.match(row[0].strip())
        if not m:
            continue
        item_name = m.group(1).title()
        # Current-week price is the column right after the second
        # "From ... to ..." header cell -- both weekly-window columns carry
        # a merged-cell None to their right, so the value always sits at
        # index 7 in the flattened row (verified live 2026-09-01 against
        # the "4Q2025"-era report layout: index 5 = prior week, index 7 =
        # current week).
        try:
            price = float(str(row[7]).strip())
        except (TypeError, ValueError, IndexError):
            continue
        rec = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "weekly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": "07.2.2",
            "source_url": url,
            "notes": "Cayman-wide network average, publisher's own aggregation",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        rec["observation_hash"] = make_hash(rec, _IDENT)
        out.append(rec)
    return out


def fetch_ky_ofreg_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    pdf_urls = _find_pdf_urls(session)
    if not pdf_urls:
        logger.warning("[%s] no fuel-price PDF links found", _SOURCE_KEY)
        return None
    all_rows: list[dict] = []
    for pdf_url in pdf_urls:
        try:
            resp = session.get(pdf_url, timeout=60)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] PDF fetch failed for %s: %s", _SOURCE_KEY, pdf_url, exc
            )
            continue
        all_rows.extend(_rows_from_pdf(resp.content, pdf_url, cutoff))
    logger.info(
        "[%s] %d rows from %d reports (cutoff=%s)",
        _SOURCE_KEY,
        len(all_rows),
        len(pdf_urls),
        cutoff,
    )
    return pd.DataFrame(all_rows) if all_rows else None
