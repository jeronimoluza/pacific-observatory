"""Hong Kong AFCD fresh-food wholesale prices — full daily catalogue.

The Agriculture, Fisheries and Conservation Department publishes a single daily
CSV of average wholesale prices at the Cheung Sha Wan / FMO markets covering
live animals (pig, cattle, chicken), marine fish, freshwater fish, vegetables,
and eggs — the only clean EAP source for the live-animal (COICOP 01.1.2.1.x)
leaves, which retail never carries. One file, all commodities: this fetcher is
general on purpose (grab everything, not just the missing leaves).

The file is a same-day snapshot ("PRICE (THIS MORNING)") stamped with a
"Last Revision Date"; this fetcher reads that date as the observation date and
accumulates history across runs. Prices are HK$/catty (HK$/egg for eggs);
missing values are marked "-" and skipped. COICOP is deferred to the downstream
classifier — item names are the English FOOD TYPE plus supply origin.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = (
    "https://www.afcd.gov.hk/english/agriculture/agr_fresh/files/Wholesale_Prices.csv"
)
_COUNTRY = "Hong Kong"
_CURRENCY = "HKD"
_SOURCE_KEY = "hk_afcd_wholesale"
_IDENT = ["source_key", "observation_date", "item_name"]

_C_CAT = "FRESH FOOD CATEGORY"
_C_TYPE = "FOOD TYPE"
_C_PRICE = "PRICE (THIS MORNING)"
_C_UNIT = "UNIT"
_C_SUPPLY = "SOURCE OF SUPPLY (IF APPROPRIATE)"
_C_INTAKE = "INTAKE DATE"
_C_PROVIDER = "PROVIDED BY"
_C_REV = "Last Revision Date"
_C_CN = "食品種類"

_NULLS = {"-", "", "n.a.", "na", "nil"}


def _unit(raw: str) -> str:
    s = (raw or "").strip().strip("()").strip()
    low = s.lower()
    if "egg" in low:
        return "egg"
    if "catty" in low:
        return "catty"
    return s.replace("$ / ", "").strip() or "catty"


def _rows(df: pd.DataFrame, cutoff: date) -> list[dict]:
    out: list[dict] = []
    ts = get_scrape_ts()
    for _, r in df.iterrows():
        food = str(r.get(_C_TYPE, "")).strip()
        # Skip the section-header rows the file repeats between categories.
        if not food or food == _C_TYPE:
            continue
        raw_price = str(r.get(_C_PRICE, "")).strip()
        if raw_price.lower() in _NULLS:
            continue
        try:
            price = float(raw_price.replace(",", ""))
        except ValueError:
            continue
        if not 0 < price < 1_000_000:
            continue
        rev = str(r.get(_C_REV, "")).strip()
        try:
            obs_date = pd.to_datetime(rev, dayfirst=True).date()
        except (ValueError, TypeError):
            continue
        if obs_date <= cutoff:
            continue

        supply = str(r.get(_C_SUPPLY, "")).strip()
        name = food if supply in _NULLS or supply == "" else f"{food} ({supply})"
        cat = str(r.get(_C_CAT, "")).strip()
        cn = str(r.get(_C_CN, "")).strip()
        provider = str(r.get(_C_PROVIDER, "")).strip()
        intake = str(r.get(_C_INTAKE, "")).strip().strip("()")
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _unit(str(r.get(_C_UNIT, ""))),
            "source_url": _URL,
            "notes": f"wholesale {cat}; {cn}; provider={provider}; intake={intake}".strip(),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_hk_afcd_wholesale(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] fetch failed: %s", _SOURCE_KEY, exc)
        return None
    resp.encoding = resp.apparent_encoding or "utf-8"
    df = pd.read_csv(io.StringIO(resp.text))
    rows = _rows(df, cutoff)
    # A single file carries one supply origin per food type per day, but the
    # "Last Revision Date" can lag the header date — dedupe defensively.
    seen: set = set()
    uniq: list[dict] = []
    for r in rows:
        key = (r["item_name"], r["observation_date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(uniq), cutoff)
    return pd.DataFrame(uniq) if uniq else None
