"""N.V. EBS (Energie Bedrijven Suriname) -- regulated electricity tariffs.

nvebs.com/elektriciteit/stroomtarieven renders two clean HTML `<table>`
elements (confirmed live 2026-09-01, `pandas.read_html` parses both
directly, no OCR/PDF involved):

  Table 0 -- monthly base fee ("Basistarief") per connection category,
  SRD/month, 6 rows (LS-Huishoudelijke/Niet-Huishoudelijke x 1/2/3 Fase).
  Table 1 -- consumption tariff ("Verbruikstarief") per kWh, 5 data rows:
  4 residential usage tiers ("Schijf 1-4") plus 1 flat non-residential
  rate.

The page states the tariffs are "geldig per DECEMBER 2024" (valid from
December 2024) -- taken as `effective_from` for both tables. Larger
tariff structures on the same page (Groot verbruiker 1/2, Sociale
instellingen, Reclame Borden, Teruglevering) are NOT parsed here: their
own tables are irregular/multi-header and cover a tiny customer segment
each -- the two tables above already cover the residential + standard
commercial tariff that matters for a PPP electricity-price series.
"""

from __future__ import annotations

import html
import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://nvebs.com/elektriciteit/stroomtarieven"
_COUNTRY = "Suriname"
_CURRENCY = "SRD"
_SOURCE_KEY = "sr_ebs_tariff"
_COICOP = "04.5.1"  # Electricity

_IDENT = ["source_key", "effective_from", "item_name"]

_EFFECTIVE_RE = re.compile(r"per\s+verbruiksmaand\s+([a-z]+)\s+(\d{4})", re.IGNORECASE)
_MONTH_NUM = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


def _effective_from(text: str) -> date | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    month = _MONTH_NUM.get(m.group(1).lower())
    if month is None:
        return None
    return date(int(m.group(2)), month, 1)


def fetch_sr_ebs_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    text = re.sub(r"<[^>]+>", " ", resp.text)
    prev = None
    while prev != text:
        prev, text = text, html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    effective_from = _effective_from(text)
    if effective_from is None:
        logger.warning(
            "[%s] Could not find 'geldig per <maand> <jaar>' on %s", _SOURCE_KEY, _URL
        )
        return None
    if effective_from <= cutoff:
        return None

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError:
        logger.exception(
            "[%s] pandas.read_html found no tables at %s", _SOURCE_KEY, _URL
        )
        return None
    if len(tables) < 2:
        logger.warning("[%s] Expected >=2 tables, found %d", _SOURCE_KEY, len(tables))
        return None

    rows = []

    # Table 0: base monthly fee per connection category.
    base_df = tables[0]
    for _, r in base_df.iloc[1:].iterrows():
        category, fee = r.iloc[0], r.iloc[1]
        try:
            fee_val = float(fee)
        except (TypeError, ValueError):
            continue
        item_name = f"{category} - Basistarief"
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": fee_val,
            "currency": _CURRENCY,
            "unit": "month",
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    # Table 1: consumption tariff per kWh (residential tiers + non-residential flat).
    usage_df = tables[1]
    current_category = None
    for _, r in usage_df.iloc[1:].iterrows():
        cat_cell, rate, tier = r.iloc[0], r.iloc[1], r.iloc[2]
        if isinstance(cat_cell, str) and cat_cell.strip():
            current_category = cat_cell.strip()
        try:
            rate_val = float(rate)
        except (TypeError, ValueError):
            continue
        tier_label = str(tier).strip() if pd.notna(tier) else ""
        item_name = f"{current_category} - {tier_label}".strip(" -")
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": rate_val,
            "currency": _CURRENCY,
            "unit": "kWh",
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
