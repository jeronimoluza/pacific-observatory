"""EPRA Kenya — town-level Maximum Retail Petroleum Prices.

Single HTML table at ``https://www.epra.go.ke/pump-prices`` carries every
cycle currently published, one row per (cycle, town):

    | From       | To         | Town    | Super (PMS) | Diesel (AGO) | Kerosene (IK) |
    | 15-12-2025 | 14-01-2026 | Garsen  | 184.95      | 171.90       | 155.21        |

~223 towns × monthly cycle, KES/litre. We parse the rendered ``<table
id="datatable">``, emit one observation per (cycle start, town, product),
and let the build stage average towns to a national price per cycle.

Compared to the prior release-by-release scraper (5 cities only), this
yields ~50× more granular national-average estimates per cycle.
"""

import logging
import re
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://www.epra.go.ke/pump-prices"
_COUNTRY = "Kenya"
_CURRENCY = "KES"
_SOURCE_KEY = "epra_ke_monthly"

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(
    r'<td[^>]*class="[^"]*views-field-field-([a-z0-9-]+)[^"]*"[^>]*>(.*?)</td>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")

# DD-MM-YYYY (allow single-digit day/month)
_DATE_RE = re.compile(r"^\s*([0-3]?\d)-([01]?\d)-(20\d{2})\s*$")

_PRODUCT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("super-pms", "PMS"),
    ("diesel-ago", "AGO"),
    ("kerosene-ik", "IK"),
)


def _clean_cell(html: str) -> str:
    return _TAG_RE.sub("", html).strip()


def _parse_date(value: str) -> date | None:
    m = _DATE_RE.match(value)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _parse_price(value: str) -> float | None:
    text = value.replace(",", "").strip()
    if not text:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    if price <= 0:
        return None
    return price


def _parse_table(html: str) -> list[dict]:
    rows: list[dict] = []
    for row_match in _ROW_RE.finditer(html):
        cells: dict[str, str] = {}
        for cell_match in _CELL_RE.finditer(row_match.group(1)):
            key = cell_match.group(1).lower()
            cells[key] = _clean_cell(cell_match.group(2))
        if "from" not in cells or "pump-town" not in cells:
            continue
        obs_date = _parse_date(cells["from"])
        if obs_date is None:
            continue
        town = cells["pump-town"]
        if not town:
            continue
        for col_key, product in _PRODUCT_COLUMNS:
            price = _parse_price(cells.get(col_key, ""))
            if price is None:
                continue
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                    "city": town,
                }
            )
    return rows


def fetch_epra_ke(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()
    parsed = _parse_table(resp.text)
    if not parsed:
        logger.warning("[epra_ke] table parser yielded zero rows")
        return None

    cutoff_iso = cutoff.isoformat()
    fresh = [r for r in parsed if r["observation_date"] > cutoff_iso]
    if not fresh:
        logger.info(
            "[epra_ke] %d table rows, none newer than cutoff %s", len(parsed), cutoff
        )
        return None

    df = (
        pd.DataFrame(fresh)
        .sort_values(["observation_date", "city", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[epra_ke] %d rows (%s → %s, %d cycles × %d towns × %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["city"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_epra_ke"]
