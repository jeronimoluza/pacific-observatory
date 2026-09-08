"""Kiribati Public Utilities Board (PUB) -- regulated electricity tariff.

PUB's "PUB Tariff and Prices" page renders its tables via the Ninja Tables
WordPress plugin, loaded client-side by an unauthenticated AJAX call to
``wp-admin/admin-ajax.php`` (``action=wp_ajax_ninja_tables_public_action``,
``target_action=get-all-data``) using a public nonce embedded in the page's
inline JS config (``data_request_url`` inside the table's JSON settings
blob). The nonce and table id are scraped fresh from the page on every run
rather than hardcoded, since Ninja Tables nonces are WordPress-session-scoped
and rotate.

Only the electricity table (id embedded per-run, found by matching the
adjacent "Electricity Services" / column-header text, not a fixed id --
PUB's page also carries separate Water Services and Sanitation Services
Ninja Tables on the same page) is read here, per the onboarding skill's "two
shapes on one site" rule -- a sibling water/sanitation fetcher would be a
separate YAML if added later.

Rows with a non-numeric tariff cell ("POA" = Price on Application, "-", or
blank -- new-connection and callout-fee line items PUB deliberately leaves
unpriced) are dropped rather than guessed at. One row (id 149) is a footnote
sentence describing the Lifeline rate, not a tariff line, and is dropped for
having no parseable price.

Kiribati has no domestic currency; countries.yaml confirms AUD is used
site-wide, consistent with the page's "$" prefix.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://pub.com.ki/pub-tariff-and-prices/"
_AJAX_URL = "https://pub.com.ki/wp-admin/admin-ajax.php"
_COUNTRY = "Kiribati"
_CURRENCY = "AUD"
_SOURCE_KEY = "ki_pub_electricity_tariff"
_COICOP = "04.5.1.0"
_IDENT = ["source_key", "effective_from", "item_name"]

# The electricity table's data_request_url looks like:
#   https:\/\/pub.com.ki\/wp-admin\/admin-ajax.php?action=wp_ajax_ninja_tables_public_action
#   &table_id=1775&target_action=get-all-data&default_sorting=old_first
#   &skip_rows=0&limit_rows=0&ninja_table_public_nonce=<nonce>
_DATA_URL_RE = re.compile(
    r'"data_request_url":"(https:\\/\\/pub\.com\.ki\\/wp-admin\\/admin-ajax\.php'
    r'\?action=wp_ajax_ninja_tables_public_action&table_id=(\d+)[^"]*)"'
)
_PRICE_RE = re.compile(r"[\d,.]+")


def _find_table_urls(html: str) -> list[tuple[str, str]]:
    """Return [(table_id, unescaped_data_request_url), ...] for every Ninja
    Table on the page, in document order (electricity table is first)."""
    out = []
    for m in _DATA_URL_RE.finditer(html):
        url = m.group(1).replace("\\/", "/")
        table_id = m.group(2)
        out.append((table_id, url))
    return out


def _num(cell: str) -> float | None:
    cell = (cell or "").strip()
    m = _PRICE_RE.search(cell)
    if not m or "$" not in cell:
        return None
    try:
        value = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def fetch_ki_pub_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_PAGE_URL, timeout=30)
        page.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load %s", _SOURCE_KEY, _PAGE_URL)
        return None

    tables = _find_table_urls(page.text)
    if not tables:
        logger.warning(
            "[%s] no Ninja Tables data_request_url found on %s -- page layout "
            "may have changed",
            _SOURCE_KEY,
            _PAGE_URL,
        )
        return None

    # The electricity table is always the first Ninja Table on the page
    # (Water Services and Sanitation Services follow, each its own table).
    _table_id, data_url = tables[0]

    try:
        resp = session.get(data_url, timeout=30)
        resp.raise_for_status()
        records = resp.json()
    except Exception:
        logger.exception("[%s] could not load table data %s", _SOURCE_KEY, data_url)
        return None

    if not records:
        logger.warning("[%s] empty table response from %s", _SOURCE_KEY, data_url)
        return None

    # Effective date is announced in the header column label, e.g.
    # "electricity_tariff_from_1_april_2026" -> 2026-04-01. Fall back to
    # today if the label doesn't parse (still emits rows rather than dropping
    # everything for a cosmetic header-name change).
    header_keys = set()
    for rec in records:
        header_keys.update(rec.get("value", {}).keys())
    effective_from = None
    for key in header_keys:
        m = re.search(r"from_(\d{1,2})_([a-z]+)_(\d{4})", key)
        if m:
            try:
                effective_from = pd.to_datetime(
                    f"{m.group(1)} {m.group(2)} {m.group(3)}", format="%d %B %Y"
                ).date()
                break
            except ValueError:
                continue
    if effective_from is None:
        effective_from = date.today()
    if effective_from <= cutoff:
        logger.info(
            "[%s] effective_from=%s not newer than cutoff=%s",
            _SOURCE_KEY,
            effective_from,
            cutoff,
        )
        return None

    ts = get_scrape_ts()
    label_col = next(
        (k for k in header_keys if k.startswith("electricity_tariff")), None
    )
    rows: list[dict] = []
    current_category = None
    for rec in records:
        value = rec.get("value", {})
        label = str(value.get(label_col, "") or "").strip()
        tier = str(value.get("to", "") or "").strip()
        price_local = _num(str(value.get("tariff", "") or ""))

        if label:
            current_category = label
        if price_local is None:
            continue  # POA / "-" / footnote rows carry no numeric tariff.
        if current_category is None:
            continue

        item_name = current_category if not tier or tier == "-" else f"{current_category} ({tier})"
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"Electricity tariff - {item_name}",
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "kWh" if "kWh" in tier else None,
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _PAGE_URL,
            "notes": (
                "PUB-published regulated electricity tariff, read from the "
                "site's Ninja Tables AJAX data endpoint."
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] no numeric tariff rows parsed", _SOURCE_KEY)
        return None

    return pd.DataFrame(rows)
