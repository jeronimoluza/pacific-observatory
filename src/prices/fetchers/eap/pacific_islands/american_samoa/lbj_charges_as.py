"""LBJ Tropical Medical Center (American Samoa) hospital standard charges."""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://lbjtmc.org/price-transparency/"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_lbj_charges"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

# The published page links a CMS-format machine-readable standard-charges file
# hosted by the hospital's price-transparency vendor. The link carries a
# per-hospital token, so it is read off the page rather than hard-coded.
_EXPORT_RE = re.compile(
    r"https://[^\"'\s]*/ptapp/api/cdm/export/oneclick\?recno=[0-9a-f]+"
)

# CMS revenue codes 0100-0219 are room-and-board lines, i.e. care that requires
# an overnight stay (COICOP 06.3.1.0). Everything else in a hospital charge
# master is ancillary/outpatient curative care (COICOP 06.2.3.1).
_COICOP_INPATIENT = "06.3.1.0"
_COICOP_OUTPATIENT = "06.2.3.1"


def _coicop_for(revenue_code: str | None) -> str:
    try:
        rc = int(str(revenue_code).strip())
    except (TypeError, ValueError):
        return _COICOP_OUTPATIENT
    return _COICOP_INPATIENT if 100 <= rc <= 219 else _COICOP_OUTPATIENT


def _parse_last_updated(value: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _clean(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _price(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _item_name(row: pd.Series) -> str:
    description = _clean(row.get("description", ""))
    parts = []
    for code_col, type_col in (("code|2", "code|2|type"), ("code|1", "code|1|type")):
        code = _clean(row.get(code_col, ""))
        code_type = _clean(row.get(type_col, ""))
        if code and code.lower() != "nan":
            parts.append(f"{code_type} {code}".strip())
    suffix = f" ({'; '.join(parts)})" if parts else ""
    return f"{description}{suffix}"[:500]


def fetch_as_lbj_charges(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})

    page = session.get(_URL, timeout=60)
    page.raise_for_status()
    match = _EXPORT_RE.search(page.text)
    if match is None:
        logger.warning("[%s] no standard-charges export link on %s", _SOURCE_KEY, _URL)
        return None
    export_url = match.group(0)

    resp = session.get(export_url, timeout=300)
    resp.raise_for_status()
    raw = resp.content.decode("utf-8", errors="replace")

    # Row 0 = metadata header, row 1 = metadata values, row 2 = the real
    # header. The two metadata rows have mismatched field counts (the value row
    # carries a trailing empty field), which makes pandas silently shift the
    # columns, so they are read with the stdlib reader instead.
    reader = csv.reader(io.StringIO(raw))
    meta_header = next(reader, [])
    meta_values = next(reader, [])
    meta = dict(zip(meta_header, meta_values))
    last_updated = _parse_last_updated(meta.get("last_updated_on", ""))
    if last_updated is None:
        logger.warning("[%s] unparseable last_updated_on; skipping", _SOURCE_KEY)
        return None
    if last_updated <= cutoff:
        logger.info(
            "[%s] file last updated %s <= cutoff %s; no new rows",
            _SOURCE_KEY,
            last_updated,
            cutoff,
        )
        return None

    df = pd.read_csv(io.StringIO(raw), skiprows=2, dtype=str, low_memory=False)
    ts = get_scrape_ts()
    observation_date = last_updated.isoformat()

    rows: list[dict] = []
    dropped = 0
    for _, item in df.iterrows():
        price = _price(item.get("standard_charge|discounted_cash"))
        basis = "discounted cash price"
        if price is None:
            price = _price(item.get("standard_charge|gross"))
            basis = "gross charge"
        name = _item_name(item)
        if price is None or not _clean(item.get("description", "")):
            dropped += 1
            continue
        row = {
            "observation_date": observation_date,
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "subnational_area": "Pago Pago",
            "source_key": _SOURCE_KEY,
            "coicop_code": _coicop_for(item.get("code|1")),
            "item_name": name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": "service",
            "source_url": _URL,
            "notes": (
                f"LBJ Tropical Medical Center standard charge ({basis}); "
                f"revenue_code={_clean(item.get('code|1', ''))}; "
                f"setting={_clean(item.get('setting', ''))}"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["observation_hash"])
    logger.info(
        "[%s] parsed %d charge rows (%d dropped, last_updated=%s)",
        _SOURCE_KEY,
        len(out),
        dropped,
        last_updated,
    )
    return out
