"""Electric Power Corporation (Samoa) — electricity tariff schedule.

Scrapes the static HTML tariff page at epc.ws/electricity-rates/. Each
consumer class's tariff is an `<h5>` heading ("Non-Domestic Consumers on
Prepaid Meters will be charged with the following tariff:", etc) followed
by a plain HTML `<table>` (kwh/units band -> Total Cost per Unit, in WST).
No JS execution required.

Two headings on the page have NO table (a "TARIFF FOR 100 LARGEST
CONSUMERS" section is an embedded image with no text layer, and a
"domestic tariff unaffected" notice is prose only) -- both are skipped;
only the four headings with a following table are extracted.

Source URL: https://www.epc.ws/electricity-rates/
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.epc.ws/electricity-rates/"
_COUNTRY = "Samoa"
_CURRENCY = "WST"
_SOURCE_KEY = "epc_electricity_tariff"
_COICOP_CODE = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"[\d.]+")


def _heading_text(h5) -> str:
    return re.sub(r"\s+", " ", h5.get_text(" ", strip=True)).strip()


def _extract_tariffs(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    for h5 in soup.find_all("h5"):
        label = _heading_text(h5)
        if "tariff" not in label.lower():
            continue
        # Walk forward to the next <table>, stopping if another <h5> appears
        # first (meaning this heading has no table -- e.g. the "100 largest
        # consumers" image section, or a prose-only notice).
        table = None
        for sib in h5.find_all_next():
            if sib.name == "h5":
                break
            if sib.name == "table":
                table = sib
                break
        if table is None:
            logger.info("[%s] no table for heading: %s", _SOURCE_KEY, label)
            continue

        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        # Header row may or may not carry real column names (one of the
        # site's four tables ships without a <thead>, header text lands in
        # the first <tr> instead) -- skip a row whose first cell isn't a
        # kWh band.
        data_rows = trs[1:] if "kwh" in trs[0].get_text(" ", strip=True).lower() else trs

        for tr in data_rows:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            band, price_text = cells[0], cells[1]
            if "kwh" in band.lower() and "cost" in price_text.lower():
                continue  # header row leaked into the body
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price_local = float(m.group(0))

            item_name = f"EPC Samoa electricity tariff, {label}, {band}"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "kWh",
                "source_url": _URL,
                "notes": f"consumer_class={label}, band={band}",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_epc_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = _extract_tariffs(soup, obs_date)
    if not rows:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning(
            "[%s] %d duplicate observation_hash rows before de-dup",
            _SOURCE_KEY,
            dup_count,
        )
        df = df.drop_duplicates(subset="observation_hash")
    return df
