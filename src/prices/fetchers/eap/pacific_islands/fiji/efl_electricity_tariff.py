"""Energy Fiji Limited (EFL) -- electricity tariffs and rates.

EFL publishes its regulated electricity tariff schedule across four static
WordPress pages (Domestic, Small Business, Other, Maximum Demand), each a
plain HTML table stamped "Prices are effective as of 1st October 2019." This
fetcher combines all four into one Fiji electricity-tariff source rather
than splitting per page, because they are one regulatory schedule (all set
by the Fiji Commerce Commission) rather than distinct sources.

The Domestic page's own HTML table is internally confusing -- a "Govt
Subsidy Yes/No" 3-column table where BOTH rows show the same 34.01 cents
figure, which does not match the page's own prose ("customer will pay
17.67 cents per unit" for the first 100 subsidized units). Rather than guess
at the source's intent, this fetcher takes only the single unambiguous
headline figure stated in prose ("The regulated domestic tariff ... is
34.01 cents/units") and skips that table entirely. Flagged loudly per
onboarding rule on rate-vs-shelf-price / ambiguous-table caveats.

Cents-denominated rates are normalized to whole FJD (divide by 100) so
price_local is always in FJD regardless of the billing unit (per kWh, per
kW, or per kVarh) -- unit records what it's charged per. The Maximum Demand
page holds three separate HTML tables (one per demand band); each table's
own header row states its band, which is used as part of item_name.

Verified live 2026-09-06: 16 tariff line items across the four pages
(1 domestic + 3 small-business + 3 other + 9 maximum-demand).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_DOMESTIC_URL = "https://efl.com.fj/your-home/electricity-tariffs-and-rates/"
_SMALL_BIZ_URL = (
    "https://efl.com.fj/your-business/electricity-tariffs-and-rates/"
    "small-business-tariffs/"
)
_OTHER_URL = (
    "https://efl.com.fj/your-business/electricity-tariffs-and-rates/other-tariffs/"
)
_MAX_DEMAND_URL = (
    "https://efl.com.fj/your-business/electricity-tariffs-and-rates/"
    "maximum-demand-tariffs/"
)

_COUNTRY = "Fiji"
_CURRENCY = "FJD"
_SOURCE_KEY = "fj_efl_electricity_tariff"
_COICOP = "04.5.1.0"
_IDENT = ["source_key", "effective_from", "item_name"]

_DOMESTIC_RATE_RE = re.compile(
    r"regulated domestic tariff.*?is\s+([\d.]+)\s*cents", re.I | re.S
)
_EFFECTIVE_RE = re.compile(
    r"effective as of\s+(\d{1,2})[a-z]{2}\s+([A-Za-z]+)\s+(\d{4})", re.I
)


def _parse_effective_date(text: str) -> date | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    day, month, year = m.groups()
    return pd.to_datetime(f"{day} {month} {year}", format="%d %B %Y").date()


def _price_to_fjd(text: str) -> tuple[float, str] | None:
    """Parse '34.01 cents' -> (0.3401, 'kWh'); '$35.33' -> (35.33, 'kW')."""
    text = text.strip()
    m = re.search(r"([\d,.]+)\s*cents", text, re.I)
    if m:
        try:
            return round(float(m.group(1).replace(",", "")) / 100.0, 6), "kWh"
        except ValueError:
            return None
    m = re.search(r"\$\s*([\d,.]+)", text)
    if m:
        try:
            return float(m.group(1).replace(",", "")), "kW"
        except ValueError:
            return None
    return None


def _unit_from_label(label: str, default: str) -> str:
    label_l = label.lower()
    if "kvarh" in label_l:
        return "kVarh"
    if "per kw" in label_l or "demand charge" in label_l:
        return "kW"
    if "kwh" in label_l:
        return "kWh"
    return default


def _fetch_page(session, url: str) -> str:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def _rows_from_simple_table(html: str, section: str) -> list[dict]:
    """One-table pages (Small Business, Other): first row is the header."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []
    out = []
    for tr in table.find_all("tr")[1:]:  # skip header row
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label, price_text = cells[0], cells[-1]
        parsed = _price_to_fjd(price_text)
        if not parsed:
            continue
        price_local, default_unit = parsed
        unit = _unit_from_label(label, default_unit)
        out.append(
            {
                "item_name": f"Electricity tariff – {section} ({label})",
                "price_local": price_local,
                "unit": unit,
            }
        )
    return out


def _rows_from_banded_tables(html: str, section: str) -> list[dict]:
    """Maximum Demand page: multiple tables, each headed by its own band."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]
        band = header_cells[0] if header_cells else "unknown band"
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label, price_text = cells[0], cells[-1]
            parsed = _price_to_fjd(price_text)
            if not parsed:
                continue
            price_local, default_unit = parsed
            unit = _unit_from_label(label, default_unit)
            out.append(
                {
                    "item_name": f"Electricity tariff – {section} {band} ({label})",
                    "price_local": price_local,
                    "unit": unit,
                }
            )
    return out


def fetch_fj_efl_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    domestic_html = _fetch_page(session, _DOMESTIC_URL)
    text = BeautifulSoup(domestic_html, "lxml").get_text(" ", strip=True)
    effective_from = _parse_effective_date(text)
    if effective_from is None:
        logger.warning(
            "[%s] Could not parse effective date from domestic page", _SOURCE_KEY
        )
        return None

    if effective_from <= cutoff:
        logger.info("[%s] No new data since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    parsed_rows: list[dict] = []

    m = _DOMESTIC_RATE_RE.search(text)
    if m:
        parsed_rows.append(
            {
                "item_name": "Electricity tariff – Domestic",
                "price_local": round(float(m.group(1)) / 100.0, 6),
                "unit": "kWh",
                "source_url": _DOMESTIC_URL,
            }
        )
    else:
        logger.warning("[%s] Could not parse domestic headline rate", _SOURCE_KEY)

    small_biz_html = _fetch_page(session, _SMALL_BIZ_URL)
    for r in _rows_from_simple_table(small_biz_html, "Small Business"):
        r["source_url"] = _SMALL_BIZ_URL
        parsed_rows.append(r)

    other_html = _fetch_page(session, _OTHER_URL)
    for r in _rows_from_simple_table(other_html, "Other"):
        r["source_url"] = _OTHER_URL
        parsed_rows.append(r)

    max_demand_html = _fetch_page(session, _MAX_DEMAND_URL)
    for r in _rows_from_banded_tables(max_demand_html, "Maximum Demand"):
        r["source_url"] = _MAX_DEMAND_URL
        parsed_rows.append(r)

    rows = []
    for item in parsed_rows:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": item["source_url"],
            "notes": "EFL-published regulated rate; cents normalized to whole FJD.",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
