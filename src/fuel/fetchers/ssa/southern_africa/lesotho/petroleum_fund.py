"""Lesotho Petroleum Fund — monthly Fuel Price Reports.

Source: https://petroleum.org.ls/fuel-price-reports/

Each monthly PDF contains a "Public Prices" table whose row
"Pump Price including 15% VAT" lists pump prices in Lisente (cents) for four
products: Petrol 93, Petrol 95, Diesel 50ppm, Illuminating Paraffin (IP).
Prices are returned in Maloti per litre, dated to the first of the report's
month.
"""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://petroleum.org.ls"
_INDEX_URL = f"{_BASE_URL}/fuel-price-reports/"
_COUNTRY = "Lesotho"
_CURRENCY = "LSL"
_SOURCE_KEY = "petroleum_fund_ls_monthly"
_THROTTLE_S = 0.8
_MAX_PAGES = 20

_TITLE_RE = re.compile(
    r"^\s*Fuel\s+Price\s+Report\s+[A-Za-z]+\s+\d{4}\s*$", re.IGNORECASE
)
_SLUG_RE = re.compile(
    r"/download/(?:lesotho-)?fuel-price-(?:report|for)-([a-z]+)-(\d{4})/?",
    re.IGNORECASE,
)
_PUMP_PRICE_RE = re.compile(
    r"Pump\s*Price\s*including\s*15%\s*VAT\s+(\d{3,5})\s+(\d{3,5})\s+(\d{3,5})\s+(\d{3,5})",
    re.IGNORECASE,
)
_MONTHS = {
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
_PRODUCTS = ("Petrol 93", "Petrol 95", "Diesel", "Domestic Paraffin")


def _date_from_url(url: str) -> date | None:
    m = _SLUG_RE.search(url)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if month is None:
        return None
    try:
        return date(int(m.group(2)), month, 1)
    except ValueError:
        return None


def _discover_reports(session) -> list[tuple[date, str, str]]:
    out: dict[date, tuple[str, str]] = {}
    for page in range(1, _MAX_PAGES + 1):
        url = _INDEX_URL if page == 1 else f"{_INDEX_URL}?cp={page}"
        try:
            resp = session.get(url, timeout=45)
        except Exception:
            logger.exception("[petroleum_fund_ls] index fetch failed: %s", url)
            break
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        page_new = 0
        for strong in soup.find_all("strong", class_="ptitle"):
            title = re.sub(r"\s+", " ", strong.get_text(" ")).strip()
            if not _TITLE_RE.match(title):
                continue
            container = strong.find_parent(attrs={"data-downloadurl": True})
            if container is None:
                holder = strong.find_parent()
                container = (
                    holder.find(attrs={"data-downloadurl": True}) if holder else None
                )
            if container is None:
                continue
            download_url = container.attrs.get("data-downloadurl")
            if not download_url:
                continue
            obs_date = _date_from_url(download_url)
            if obs_date is None or obs_date in out:
                continue
            out[obs_date] = (title, download_url)
            page_new += 1
        logger.info(
            "[petroleum_fund_ls] page=%d new=%d total=%d", page, page_new, len(out)
        )
        if page_new == 0 and page > 1:
            break
        time.sleep(_THROTTLE_S)
    return sorted((d, t, u) for d, (t, u) in out.items())


def _pump_prices(pdf_bytes: bytes) -> tuple[int, int, int, int] | None:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[petroleum_fund_ls] pdfplumber not installed")
        return None
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                m = _PUMP_PRICE_RE.search(text)
                if m:
                    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]
                # Letter-spaced fallback (older reports). Merge adjacent digit chars
                # into multi-digit numbers via a wider x_tolerance, then locate the
                # row directly above the "Pump Price ..." label.
                words = page.extract_words(x_tolerance=14, y_tolerance=2)
                if not words:
                    continue
                rows: dict[int, list[dict]] = {}
                for w in words:
                    rows.setdefault(round(w["top"]), []).append(w)
                ys = sorted(rows)
                for idx, y in enumerate(ys):
                    line = " ".join(
                        w["text"] for w in sorted(rows[y], key=lambda w: w["x0"])
                    )
                    if "Pump Price" not in line and "PumpPrice" not in line.replace(
                        " ", ""
                    ):
                        continue
                    # numbers may be on the label row or the row immediately above
                    for cand_y in (y, ys[idx - 1] if idx > 0 else None):
                        if cand_y is None:
                            continue
                        nums = [
                            w["text"]
                            for w in sorted(rows[cand_y], key=lambda w: w["x0"])
                            if w["text"].isdigit() and 3 <= len(w["text"]) <= 5
                        ]
                        if len(nums) == 4:
                            return tuple(int(n) for n in nums)  # type: ignore[return-value]
    except Exception:
        logger.exception("[petroleum_fund_ls] PDF parse failed")
    return None


def fetch_petroleum_fund_ls(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for obs_date, title, url in _discover_reports(session):
        if obs_date <= cutoff:
            continue
        try:
            resp = session.get(url, timeout=60, allow_redirects=True)
        except Exception:
            logger.exception("[petroleum_fund_ls] download failed: %s", url)
            continue
        if resp.status_code != 200 or resp.content[:4] != b"%PDF":
            logger.warning(
                "[petroleum_fund_ls] %s: status=%s ct=%s",
                title,
                resp.status_code,
                resp.headers.get("Content-Type", ""),
            )
            continue
        prices = _pump_prices(resp.content)
        if prices is None:
            logger.warning("[petroleum_fund_ls] no prices parsed for %s", title)
            continue
        for product, lisente in zip(_PRODUCTS, prices):
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(lisente / 100, 2),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
        logger.info("[petroleum_fund_ls] %s → %s", obs_date, prices)
        time.sleep(_THROTTLE_S)

    if not rows:
        logger.info("[petroleum_fund_ls] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[petroleum_fund_ls] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_petroleum_fund_ls"]
