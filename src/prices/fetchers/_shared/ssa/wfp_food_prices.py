"""WFP food prices (via HDX) — shared SSA fetcher, one country per callable.

The World Food Programme's price database, republished country-by-country on the
Humanitarian Data Exchange, is the broadest public source of average retail AND
wholesale prices for the staple food commodities that supermarket catalogues do
not carry — cereals, pulses, tubers, live animals, fresh/dried fish, leafy
greens, oils, sugar — across Sub-Saharan Africa. Each country dataset is a
single CSV of per-market monthly observations reaching back years; between
these fifteen SSA panels this is a general division-01 `official_avg` feed,
not a targeted extractor.

One shared module, one public ``fetch_wfp_<iso3>`` per country (Bucket-2). The
CSV download URL is resolved at run time from the dataset's stable HDX slug via
the CKAN API, so a resource-UUID change does not break the fetcher. Per-market
rows are collapsed to a national monthly average per (commodity, unit, currency,
price type); the market count and USD value are kept in ``notes`` and the retail
vs wholesale split is kept in the dedup hash. COICOP is deferred to the
downstream classifier — ``item_name`` is WFP's English commodity label.
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
    "sen": ("Senegal", "wfp-food-prices-for-senegal"),
    "eth": ("Ethiopia", "wfp-food-prices-for-ethiopia"),
    "mdg": ("Madagascar", "wfp-food-prices-for-madagascar"),
    "mwi": ("Malawi", "wfp-food-prices-for-malawi"),
    "mrt": ("Mauritania", "wfp-food-prices-for-mauritania"),
    "moz": ("Mozambique", "wfp-food-prices-for-mozambique"),
    "tza": (
        "United Republic of Tanzania",
        "wfp-food-prices-for-united-republic-of-tanzania",
    ),
    "zwe": ("Zimbabwe", "wfp-food-prices-for-zimbabwe"),
    "ken": ("Kenya", "wfp-food-prices-for-kenya"),
    "sdn": ("Sudan", "wfp-food-prices-for-sudan"),
    "gin": ("Guinea", "wfp-food-prices-for-guinea"),
    "cod": (
        "Democratic Republic of the Congo",
        "wfp-food-prices-for-democratic-republic-of-the-congo",
    ),
    "caf": ("Central African Republic", "wfp-food-prices-for-central-african-republic"),
    "civ": ("Cote d'Ivoire", "wfp-food-prices-for-cote-d-ivoire"),
    "rwa": ("Rwanda", "wfp-food-prices-for-rwanda"),
    "nga": ("Nigeria", "wfp-food-prices-for-nigeria"),
    "mli": ("Mali", "wfp-food-prices-for-mali"),
    "bfa": ("Burkina Faso", "wfp-food-prices-for-burkina-faso"),
    "ner": ("Niger", "wfp-food-prices-for-niger"),
    "sle": ("Sierra Leone", "wfp-food-prices-for-sierra-leone"),
    "lbr": ("Liberia", "wfp-food-prices-for-liberia"),
    "gmb": ("Gambia", "wfp-food-prices-for-gambia"),
    "uga": ("Uganda", "wfp-food-prices-for-uganda"),
    "nam": ("Namibia", "wfp-food-prices-for-namibia"),
    "swz": ("Eswatini", "wfp-food-prices-for-eswatini"),
    "tcd": ("Chad", "wfp-food-prices-for-chad"),
    "cog": ("Congo", "wfp-food-prices-for-congo"),
    "bdi": ("Burundi", "wfp-food-prices-for-burundi"),
    "som": ("Somalia", "wfp-food-prices-for-somalia"),
    "ssd": ("South Sudan", "wfp-food-prices-for-south-sudan"),
    "gnb": ("Guinea-Bissau", "wfp-food-prices-for-guinea-bissau"),
    "lso": ("Lesotho", "wfp-food-prices-for-lesotho"),
    "zmb": ("Zambia", "wfp-food-prices-for-zambia"),
    "cmr": ("Cameroon", "wfp-food-prices-for-cameroon"),
    "ben": ("Benin", "wfp-food-prices-for-benin"),
    "tgo": ("Togo", "wfp-food-prices-for-togo"),
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


def fetch_wfp_sen(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sen")


def fetch_wfp_eth(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="eth")


def fetch_wfp_mdg(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mdg")


def fetch_wfp_mwi(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mwi")


def fetch_wfp_mrt(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mrt")


def fetch_wfp_moz(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="moz")


def fetch_wfp_tza(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="tza")


def fetch_wfp_zwe(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="zwe")


def fetch_wfp_ken(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ken")


def fetch_wfp_sdn(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sdn")


def fetch_wfp_gin(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gin")


def fetch_wfp_cod(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cod")


def fetch_wfp_caf(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="caf")


def fetch_wfp_civ(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="civ")


def fetch_wfp_rwa(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="rwa")


def fetch_wfp_nga(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="nga")


def fetch_wfp_mli(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mli")


def fetch_wfp_bfa(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bfa")


def fetch_wfp_ner(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ner")


def fetch_wfp_sle(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sle")


def fetch_wfp_lbr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lbr")


def fetch_wfp_gmb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gmb")


def fetch_wfp_uga(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="uga")


def fetch_wfp_nam(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="nam")


def fetch_wfp_swz(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="swz")


def fetch_wfp_tcd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="tcd")


def fetch_wfp_cog(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cog")


def fetch_wfp_bdi(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bdi")


def fetch_wfp_som(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="som")


def fetch_wfp_ssd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ssd")


def fetch_wfp_gnb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gnb")


def fetch_wfp_lso(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lso")


def fetch_wfp_zmb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="zmb")


def fetch_wfp_cmr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cmr")


def fetch_wfp_ben(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ben")


def fetch_wfp_tgo(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="tgo")
