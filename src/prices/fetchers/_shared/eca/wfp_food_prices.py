"""WFP food prices (via HDX) — shared ECA fetcher, one country per callable.

Mirrors `_shared.ssa.wfp_food_prices` / `_shared.menaap.wfp_food_prices`: the
World Food Programme's price database, republished country-by-country on the
Humanitarian Data Exchange, gives per-market monthly observations for staple
food commodities that supermarket catalogues do not carry. Only two ECA
countries have a live per-country WFP panel as of 2026-08-06 (checked via the
CKAN package_show API against every `wfp-food-prices-for-<country>` slug
candidate): Kyrgyz Republic and Belarus. Uzbekistan and Turkmenistan have no
`wfp-food-prices-for-*` dataset on HDX (package_show 404s, and
package_search for "uzbekistan food prices" / "turkmenistan food prices"
surfaces no matching result) — not scaffolded here.

One shared module, one public ``fetch_wfp_<iso3>`` per country (Bucket-2). The
CSV download URL is resolved at run time from the dataset's stable HDX slug via
the CKAN API. Per-market rows are collapsed to a national monthly average per
(commodity, unit, currency, price type); market count and USD value are kept
in ``notes``, retail vs wholesale split is kept in the dedup hash. COICOP is
deferred to the downstream classifier — ``item_name`` is WFP's English
commodity label.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CKAN = "https://data.humdata.org/api/3/action/package_show"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "price_type"]

# repo country slug (iso3, lowercase) -> (display name, HDX dataset slug)
_PANELS: dict[str, tuple[str, str]] = {
    "kgz": ("Kyrgyzstan", "wfp-food-prices-for-kyrgyzstan"),
    "blr": ("Belarus", "wfp-food-prices-for-belarus"),
}


def _resolve_csv_url(session, hdx_slug: str) -> str | None:
    try:
        r = session.get(f"{_CKAN}?id={hdx_slug}", timeout=60)
        r.raise_for_status()
        resources = r.json()["result"]["resources"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[wfp:%s] CKAN lookup failed: %s", hdx_slug, exc)
        return None
    for res in resources:
        url = res.get("url", "")
        if res.get("format", "").upper() == "CSV" and "food_prices" in url.lower():
            return url
    logger.warning("[wfp:%s] no food_prices CSV resource found", hdx_slug)
    return None


def _read_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), low_memory=False)
    # WFP CSVs carry a HXL hashtag row (#date, #item+name, ...) below the header.
    if len(df) and str(df.iloc[0, 0]).startswith("#"):
        df = df.iloc[1:].reset_index(drop=True)
    return df


def _national_rows(
    df: pd.DataFrame, country: str, source_key: str, url: str, cutoff: date
) -> list[dict]:
    df = df.copy()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["usdprice"] = pd.to_numeric(df.get("usdprice"), errors="coerce")
    df["obs"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df[df["price"].notna() & df["obs"].notna()]
    df = df[df["price"] > 0]
    # Keep real observations; drop model forecasts.
    if "priceflag" in df.columns:
        df = df[df["priceflag"].astype(str).str.lower() != "forecast"]
    df = df[df["obs"] > cutoff]
    if df.empty:
        return []

    ts = get_scrape_ts()
    keys = ["obs", "commodity", "unit", "currency", "pricetype", "category"]
    for k in keys:
        if k not in df.columns:
            df[k] = ""
    grp = df.groupby(keys, dropna=False)
    out: list[dict] = []
    for (obs, commodity, unit, currency, pricetype, category), g in grp:
        commodity = str(commodity).strip()
        if not commodity:
            continue
        price = float(g["price"].mean())
        if not 0 < price < 1e13:
            continue
        usd = g["usdprice"].mean()
        usd_txt = f"{usd:.4f}" if pd.notna(usd) else "na"
        row = {
            "observation_date": obs.isoformat(),
            "period_kind": "monthly",
            "country": country,
            "source_key": source_key,
            "item_name": commodity,
            "price_local": round(price, 4),
            "currency": str(currency).strip() or None,
            "unit": str(unit).strip() or None,
            "source_url": url,
            "notes": (
                f"{str(pricetype).strip() or 'Retail'}; {str(category).strip()}; "
                f"national avg of {len(g)} market obs; usd~{usd_txt}"
            ),
            "scrape_ts": ts,
            "price_type": str(pricetype).strip() or "Retail",
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("price_type")
        out.append(row)
    return out


def _fetch(cutoff: date, *, iso3: str) -> pd.DataFrame | None:
    country, hdx_slug = _PANELS[iso3]
    source_key = f"wfp_{iso3}"
    session = get_session()
    url = _resolve_csv_url(session, hdx_slug)
    if not url:
        return None
    try:
        resp = session.get(url, timeout=120)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CSV fetch failed: %s", source_key, exc)
        return None
    resp.encoding = resp.apparent_encoding or "utf-8"
    rows = _national_rows(_read_csv(resp.text), country, source_key, url, cutoff)
    logger.info(
        "[%s] %d national monthly rows (cutoff=%s)", source_key, len(rows), cutoff
    )
    return pd.DataFrame(rows) if rows else None


def fetch_wfp_kgz(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="kgz")


def fetch_wfp_blr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="blr")
