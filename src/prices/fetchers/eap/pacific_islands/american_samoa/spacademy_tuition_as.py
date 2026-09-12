"""South Pacific Academy (Tafuna, American Samoa) tuition and fees."""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://southpacificacademy.com/admissions/tuition-fees/"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_spacademy_tuition"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_PRICE_RE = re.compile(r"(?P<price>\d[\d,]*\.\d{2})")

# Grade-band columns map onto COICOP education levels; the school's own
# ancillary fees are not level-specific and go to 10.5.0.9.
_COICOP_BY_BAND = {
    "K3-4th": "10.2.0.0",
    "5th-8th": "10.3.0.0",
    "9th-12th": "10.3.0.0",
}
_COICOP_OTHER = "10.5.0.9"


def _clean(value) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _price(value) -> float | None:
    match = _PRICE_RE.search(_clean(value).replace("$", ""))
    if match is None:
        return None
    return float(match.group("price").replace(",", ""))


def _row(item_name: str, price: float, unit: str, coicop: str, notes: str, ts: str):
    row = {
        "observation_date": date.today().isoformat(),
        "period_kind": "current_school_year",
        "country": _COUNTRY,
        "subnational_area": "Tafuna",
        "source_key": _SOURCE_KEY,
        "coicop_code": coicop,
        "item_name": item_name[:500],
        "price_local": round(price, 2),
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": _URL,
        "notes": notes,
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse_tuition(df: pd.DataFrame, ts: str) -> list[dict]:
    """Emit one full-year cost per grade band per payment plan."""
    bands = [c for c in df.columns if _clean(c) in _COICOP_BY_BAND]
    if not bands:
        return []
    plan_col, due_col = df.columns[0], df.columns[1]

    rows: list[dict] = []
    plan: str | None = None
    for _, item in df.iterrows():
        cell_plan = _clean(item[plan_col])
        if cell_plan and cell_plan.lower() != "nan":
            plan = cell_plan
        due = _clean(item[due_col])
        # Annual plans carry the full-year figure on their single row; the
        # instalment plans carry theirs on the TOTAL: row. Per-instalment rows
        # are skipped so the series stays comparable across plans.
        is_total = due.upper().startswith("TOTAL")
        is_annual = (plan or "").lower() == "annual"
        if not (is_total or is_annual) or plan is None:
            continue
        for band in bands:
            price = _price(item[band])
            if price is None:
                continue
            rows.append(
                _row(
                    f"School tuition, grades {_clean(band)}, {plan.lower()} plan, "
                    f"full school year",
                    price,
                    "school_year",
                    _COICOP_BY_BAND[_clean(band)],
                    f"South Pacific Academy tuition; payment plan={plan}",
                    ts,
                )
            )
    return rows


def _parse_fees(df: pd.DataFrame, ts: str) -> list[dict]:
    amount_col = df.columns[-1]
    label_col, due_col = df.columns[0], df.columns[1]
    rows: list[dict] = []
    label: str | None = None
    for _, item in df.iterrows():
        cell_label = _clean(item[label_col])
        if cell_label and cell_label.lower() != "nan":
            # The published cell glues the fee name to a paragraph of prose;
            # the name is the leading title-case run before the first sentence.
            match = re.match(r"^(.{3,60}?Fee|.{3,60}?Fees)(?=[A-Z]|$)", cell_label)
            label = _clean(match.group(1)) if match else cell_label[:60]
        price = _price(item[amount_col])
        if price is None or label is None:
            continue
        qualifier = _clean(item[due_col])
        name = label
        if qualifier and qualifier.lower() != "nan":
            name = f"{label} ({qualifier[:60]})"
        rows.append(
            _row(
                name,
                price,
                "item",
                _COICOP_OTHER,
                "South Pacific Academy ancillary school fee",
                ts,
            )
        )
    return rows


def fetch_as_spacademy_tuition(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    # The site's WAF 403s a plain requests User-Agent but serves a stock
    # browser TLS fingerprint without any further challenge.
    resp = curl_requests.get(_URL, impersonate="chrome124", timeout=60)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text))
    ts = get_scrape_ts()
    rows: list[dict] = []
    for table in tables:
        columns = {_clean(c) for c in table.columns}
        if columns & set(_COICOP_BY_BAND):
            rows.extend(_parse_tuition(table, ts))
        elif "FEES" in {c.upper() for c in columns}:
            rows.extend(_parse_fees(table, ts))

    if not rows:
        logger.warning("[%s] no tuition rows parsed", _SOURCE_KEY)
        return None
    out = pd.DataFrame(rows).drop_duplicates(subset=["observation_hash"])
    logger.info("[%s] parsed %d tuition/fee rows", _SOURCE_KEY, len(out))
    return out
