"""American Samoa Dept of Commerce CPI Newsletter averaged commodity prices.

The DOC CPI Newsletter PDFs include an item-level "Quarterly Averaged Prices"
table in addition to the index table parsed by ``doc_cpi.py``. This fetcher
keeps only the current quarter from each newsletter's rolling five-quarter
table and emits PriceObservation rows.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.eap.pacific_islands.american_samoa import _wix_faq
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_doc_cpi_avg_prices"
_IDENT = ["source_key", "observation_date", "item_name"]

_CPI_CATEGORY_TITLE = "Consumer Price Index"
_CPI_CATEGORY_ID_FALLBACK = "5e921803-3d73-4dd3-a41e-81aa1413e9c4"

_QUARTER_RE = re.compile(r"Q(?P<q>[1-4])/(?P<yy>\d{2})", re.IGNORECASE)
_VALUE_ROW_RE = re.compile(
    r"^(?P<prefix>.+?)\s+"
    r"(?P<v1>n/a|-?\d+(?:\.\d+)?)\s+"
    r"(?P<v2>n/a|-?\d+(?:\.\d+)?)\s+"
    r"(?P<v3>n/a|-?\d+(?:\.\d+)?)\s+"
    r"(?P<v4>n/a|-?\d+(?:\.\d+)?)\s+"
    r"(?P<v5>n/a|-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)

# Raw PDF label -> (canonical item name, unit, COICOP-2018 code).
_ITEMS: list[tuple[str, str, str, str]] = [
    ("Beer, Coors Light", "Beer, Coors Light", "12 fl oz", "02.1.3"),
    ("Beer, Vailima", "Beer, Vailima", "750 ml", "02.1.3"),
    ("Chicken Legs Case", "Chicken legs", "22 lbs case", "01.1.2"),
    ("Chicken-whole", "Whole chicken", "lb", "01.1.2"),
    ("Cigarettes- Benson", "Cigarettes, Benson", "pack", "02.2.0"),
    ("Cigarettes-Kools", "Cigarettes, Kools", "pack", "02.2.0"),
    ("Cooking Oil", "Cooking oil", "24 fl oz", "01.1.5"),
    ("Corned Beef", "Corned beef", "12 oz", "01.1.2"),
    ("Electricity", "Electricity tariff", "per kWh", "04.5.1"),
    ("Fresh eggs", "Fresh eggs", "dozen", "01.1.4"),
    ("Hot Dogs", "Hot dogs", "lb", "01.1.2"),
    ("Milk, fresh", "Fresh milk", "liter", "01.1.4"),
    ("Soft Drinks", "Soft drinks", "12 oz", "01.2.2"),
    ("Turkey tail", "Turkey tail", "lb", "01.1.2"),
    ("Unleaded gas", "Unleaded gasoline", "gal", "07.2.2"),
    ("Lumber (2x4x16)", "Lumber 2x4x16", "single", "04.3.1"),
    ("Cement bags", "Cement", "40 kg bag", "04.3.1"),
    ("Dry Wall (4x8)", "Drywall 4x8", "single", "04.3.1"),
    ("Exterior Paint", "Exterior paint", "gal", "04.3.1"),
    ("Gas Tank", "LPG gas tank", "20 lbs", "04.5.2"),
    ("Spaghetti", "Spaghetti", "14.75 oz", "01.1.1"),
    ("Mackerel", "Mackerel", "15 oz", "01.1.3"),
    ("Bananas", "Bananas", "lb", "01.1.6"),
    ("Butter", "Butter", "227 gm", "01.1.5"),
    ("Apple", "Apples", "lb", "01.1.6"),
    ("Beef", "Beef", "lb", "01.1.2"),
    ("Bread", "Bread", "loaf", "01.1.1"),
    ("Diesel", "Diesel", "gal", "07.2.2"),
    ("Rice", "Rice", "40 lbs", "01.1.1"),
    ("Salt", "Salt", "700 gm", "01.1.9"),
    ("Spam", "Spam", "12 oz", "01.1.2"),
    ("Sugar", "Sugar", "2 kg", "01.1.8"),
    ("Taro", "Taro", "lb", "01.1.7"),
    ("Tuna", "Tuna", "6.5 oz", "01.1.3"),
]


def _quarter_date(label: str) -> date | None:
    m = _QUARTER_RE.fullmatch(label.strip())
    if not m:
        return None
    year = 2000 + int(m.group("yy"))
    month = 1 + (int(m.group("q")) - 1) * 3
    return date(year, month, 1)


def _parse_price(raw: str) -> float | None:
    if raw.lower() == "n/a":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _match_item(prefix: str) -> tuple[str, str, str] | None:
    low = prefix.lower().strip()
    for raw_label, item_name, unit, coicop in _ITEMS:
        if low.startswith(raw_label.lower()):
            return item_name, unit, coicop
    return None


def _parse_quarterly_avg_prices(
    pdf_bytes: bytes, pdf_url: str, cutoff: date
) -> list[dict]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header_idx = None
    quarter_labels: list[str] = []
    for idx, line in enumerate(lines):
        if not line.startswith("Commodity Unit "):
            continue
        found = _QUARTER_RE.findall(line)
        if len(found) >= 5:
            header_idx = idx
            quarter_labels = _QUARTER_RE.findall(line)
            break
    if header_idx is None or not quarter_labels:
        return []

    q_num, yy = quarter_labels[-1]
    obs_date = _quarter_date(f"Q{q_num}/{yy}")
    if obs_date is None or obs_date <= cutoff:
        return []

    ts = get_scrape_ts()
    rows: list[dict] = []
    for line in lines[header_idx + 1 :]:
        if line.startswith("Annually Averaged Prices"):
            break
        m = _VALUE_ROW_RE.match(line)
        if not m:
            continue
        item = _match_item(m.group("prefix"))
        if item is None:
            logger.warning(
                "[%s] no item mapping for %r - dropping row",
                _SOURCE_KEY,
                m.group("prefix"),
            )
            continue
        price = _parse_price(m.group("v5"))
        if price is None:
            continue
        item_name, unit, coicop = item
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "item_name": item_name,
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": pdf_url,
            "notes": "American Samoa CPI Newsletter, Quarterly Averaged Prices table",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_as_doc_cpi_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )

    token = _wix_faq.get_faq_token(session, _SOURCE_KEY)
    if not token:
        return None
    category_id = _wix_faq.get_category_id(
        session, token, _CPI_CATEGORY_TITLE, _CPI_CATEGORY_ID_FALLBACK, _SOURCE_KEY
    )
    year_entries = _wix_faq.query_year_entries(session, token, category_id, _SOURCE_KEY)
    if not year_entries:
        logger.warning("[%s] no CPI year entries found", _SOURCE_KEY)
        return None

    by_hash: dict[str, dict] = {}
    skipped = 0
    for entry in year_entries:
        links = _wix_faq.extract_links(entry.get("draftjs", ""))
        for label, url in links:
            if "newsletter" not in label.lower():
                continue
            pdf_url = _wix_faq.gdrive_direct(url)
            try:
                resp = session.get(pdf_url, timeout=60)
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] PDF fetch failed for %s (%s): %s",
                    _SOURCE_KEY,
                    label,
                    pdf_url,
                    exc,
                )
                skipped += 1
                continue
            if not resp.content.startswith(b"%PDF"):
                logger.warning(
                    "[%s] non-PDF response for %s (%s)", _SOURCE_KEY, label, pdf_url
                )
                skipped += 1
                continue
            for row in _parse_quarterly_avg_prices(resp.content, pdf_url, cutoff):
                by_hash[row["observation_hash"]] = row

    rows = sorted(
        by_hash.values(), key=lambda r: (r["observation_date"], r["item_name"])
    )
    if skipped:
        logger.info("[%s] %d newsletter link(s) skipped", _SOURCE_KEY, skipped)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
