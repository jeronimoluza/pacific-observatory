"""FEWS NET market price facts — shared SSA fetcher, one country per callable.

USAID's Famine Early Warning Systems Network publishes a public REST API
(``fdw.fews.net``) of monthly market-price observations sourced from national
statistics offices and ministries of agriculture/trade across Africa — the
same staple-commodity, official-average layer as the WFP/HDX panels
(``_shared.ssa.wfp_food_prices``), but a distinct upstream agency and dataset,
so it is a genuine complementary source rather than a re-scrape. Verified
live 2026-08-07 against ``/api/marketpricefacts/``.

One shared module, one public ``fetch_fews_<iso3>`` per country (Bucket-2).
The API supports server-side date filtering via ``start_date=YYYY-MM-DD``
(confirmed: narrows the result count, unlike the undocumented
``period_date__gte`` which is silently ignored) plus ``ordering=-period_date``
for newest-first pagination — used together so a fetch only walks the pages
newer than the cutoff instead of the country's full history.

Known constraint, verified live 2026-08-07: the API hard-caps pagination
depth at ``offset=1000`` — any request past that returns HTTP 403 regardless
of ``page_size`` (confirmed with single-shot ``page_size=1000&offset=0``
too, so it is not a rate limit; ``offset=999`` succeeds, ``offset=1000``
never does). On a large first-run backfill this silently truncates to the
newest ~1000 raw facts for that country (still the most valuable slice,
since results are newest-first) and ``_fetch_pages`` logs a warning and
returns what it has rather than raising. Every subsequent run's delta is
bounded by monthly cadence, so this only bites the very first collect per
country. Per-market rows
are collapsed to a national monthly average per (commodity, unit, currency,
price_type), mirroring the WFP fetcher's aggregation; market count and the
USD common-currency value are kept in ``notes``, retail vs wholesale is kept
in the dedup hash. COICOP is deferred to the downstream classifier —
``item_name`` is FEWS NET's English product label.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API = "https://fdw.fews.net/api/marketpricefacts/"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "price_type"]
_PAGE_SIZE = 200
_MAX_PAGES = (
    500  # safety cap; a country needing more than 100k new rows is a bug, not real
)

# repo country slug (iso3, lowercase) -> (display name, FEWS NET iso2 country_code)
_COUNTRIES: dict[str, tuple[str, str]] = {
    "bwa": ("Botswana", "BW"),
    "cpv": ("Cabo Verde", "CV"),
    "ago": ("Angola", "AO"),
    "caf": ("Central African Republic", "CF"),
    "rwa": ("Rwanda", "RW"),
    "swz": ("Eswatini", "SZ"),
    "nam": ("Namibia", "NA"),
    "zwe": ("Zimbabwe", "ZW"),
    "civ": ("Cote d'Ivoire", "CI"),
    "gmb": ("Gambia", "GM"),
    "gin": ("Guinea", "GN"),
    "lbr": ("Liberia", "LR"),
    "sle": ("Sierra Leone", "SL"),
}


def _fetch_pages(session, country_code: str, cutoff: date) -> list[dict]:
    rows: list[dict] = []
    url = _API
    params = {
        "country_code": country_code,
        "ordering": "-period_date",
        "page_size": _PAGE_SIZE,
        "start_date": cutoff.isoformat(),
    }
    for _ in range(_MAX_PAGES):
        try:
            resp = session.get(url, params=params, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[fews:%s] request failed: %s", country_code, exc)
            break
        results = payload.get("results", [])
        rows.extend(results)
        nxt = payload.get("next")
        if not nxt:
            break
        url = nxt
        params = None  # `next` already carries the full query string
        time.sleep(0.4)
    return rows


def _national_rows(
    raw: list[dict], country: str, source_key: str, cutoff: date
) -> list[dict]:
    if not raw:
        return []
    df = pd.DataFrame(raw)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["common_currency_price"] = pd.to_numeric(
        df.get("common_currency_price"), errors="coerce"
    )
    df["obs"] = pd.to_datetime(df["period_date"], errors="coerce").dt.date
    df = df[df["value"].notna() & df["obs"].notna()]
    df = df[df["value"] > 0]
    df = df[df["obs"] > cutoff]
    if df.empty:
        return []

    ts = get_scrape_ts()
    keys = ["obs", "product", "unit", "currency", "price_type"]
    for k in keys:
        if k not in df.columns:
            df[k] = ""
    grp = df.groupby(keys, dropna=False)
    out: list[dict] = []
    for (obs, product, unit, currency, price_type), g in grp:
        product = str(product).strip()
        if not product:
            continue
        price = float(g["value"].mean())
        if not 0 < price < 1e13:
            continue
        usd = g["common_currency_price"].mean()
        usd_txt = f"{usd:.4f}" if pd.notna(usd) else "na"
        markets = g["market"].nunique() if "market" in g else 1
        row = {
            "observation_date": obs.isoformat(),
            "period_kind": "monthly",
            "country": country,
            "source_key": source_key,
            "item_name": product,
            "price_local": round(price, 4),
            "currency": str(currency).strip() or None,
            "unit": str(unit).strip() or None,
            "source_url": _API,
            "notes": (
                f"{str(price_type).strip() or 'Retail'}; FEWS NET national avg of "
                f"{len(g)} obs across {markets} market(s); usd~{usd_txt}"
            ),
            "scrape_ts": ts,
            "price_type_key": str(price_type).strip() or "Retail",
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("price_type_key")
        out.append(row)
    return out


def _fetch(cutoff: date, *, iso3: str) -> pd.DataFrame | None:
    country, country_code = _COUNTRIES[iso3]
    source_key = f"fews_{iso3}"
    session = get_session()
    raw = _fetch_pages(session, country_code, cutoff)
    rows = _national_rows(raw, country, source_key, cutoff)
    logger.info(
        "[%s] %d national monthly rows from %d raw facts (cutoff=%s)",
        source_key,
        len(rows),
        len(raw),
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None


def fetch_fews_bwa(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bwa")


def fetch_fews_cpv(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cpv")


def fetch_fews_ago(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ago")


def fetch_fews_caf(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="caf")


def fetch_fews_rwa(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="rwa")


def fetch_fews_swz(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="swz")


def fetch_fews_nam(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="nam")


def fetch_fews_zwe(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="zwe")


def fetch_fews_civ(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="civ")


def fetch_fews_gmb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gmb")


def fetch_fews_gin(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gin")


def fetch_fews_lbr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lbr")


def fetch_fews_sle(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sle")
