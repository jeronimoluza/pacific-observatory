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
``period_date__gte`` which is silently ignored), so a fetch only walks the
pages newer than the cutoff instead of the country's full history. The
``ordering`` param (formerly ``-period_date`` for newest-first) regressed
sometime after 2026-08-07: as of 2026-09-11, ANY ``ordering`` value
(``-period_date``, ``period_date``, ``-id``) makes the API return
HTTP 202 with an empty body instead of the JSON page, which silently broke
every country using this module (all raised "0 raw facts" without erroring).
Fixed by dropping ``ordering`` entirely — without it, results paginate in
the API's default order, which combined with ``start_date`` is ascending by
``period_date`` (verified: SS offset=0 returns 2020-01, offset=900 returns
2024-Q1), so pagination now walks forward chronologically from the cutoff
instead of backward from "now". This is actually a better fit for the
offset<1000 cap below: each run's cutoff advances to the max date fetched,
so a capped first run still resumes forward next time with no gap, whereas
newest-first-then-capped would have permanently stranded older history.

Known constraint, verified live 2026-08-07 and re-verified 2026-09-11: the
API hard-caps pagination depth at ``offset=1000`` — any request past that
offset returns HTTP 403 regardless of ``page_size`` (confirmed with
single-shot ``page_size=1000&offset=0`` too, so it is not a rate limit;
``offset=999`` succeeds, ``offset=1000`` never does). On a large first-run
backfill this truncates to the oldest ~1000 raw facts after the cutoff (see
the ordering note above); ``_fetch_pages`` catches the resulting exception
and returns what it has rather than raising. Every subsequent run resumes
from the new cutoff, so full history is recovered over several runs. Per-market rows
are collapsed to a national monthly average per (commodity, unit, currency,
price_type), mirroring the WFP fetcher's aggregation; market count and the
USD common-currency value are kept in ``notes``, retail vs wholesale is kept
in the dedup hash.

COICOP is source-curated: every emitted row carries a division-01/02 leaf
from ``_COICOP_MAP`` below, and a product the map does not cover -- the
feed's fuel, wage, soap and bulk-water series included -- is DROPPED with a
logged warning rather than emitted with a null ``coicop_code``.
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
    "ssd": ("South Sudan", "SS"),
    "bdi": ("Burundi", "BI"),
    "som": ("Somalia", "SO"),
}


# FEWS NET product label -> COICOP-2018 leaf. `coicop_classification:
# source_curated` on every fews_net manifest: FEWS NET publishes a small,
# stable English commodity vocabulary ("Millet", "Rice (Milled)"), not retail
# SKU strings, so the downstream classifier -- trained on messy supermarket
# names -- is the wrong tool. Scope is COICOP divisions 01 and 02 ONLY: the
# feed also carries fuel (Diesel, Gasoline, LPG), wage series (Agricultural
# Labor, Casual Labor), soap and bulk water, and those labels are
# deliberately absent so the fetcher drops them with a logged warning rather
# than forcing them into a food leaf. Also absent, and why:
#   * "Tea leaves (Mixed)" -- 01.2.3.0.1 (green) and 01.2.3.0.2 (black) are
#     different leaves and "Mixed" does not say which.
#   * "Water (potable, drinking)" -- priced per 200 L drum, i.e. vended water
#     supply (COICOP 04.4), not bottled water (01.2.5.0.0).
#   * "Enriched corn/bean flour" -- a blended cereal/pulse food-aid flour,
#     between 01.1.1.2.6 and 01.1.7.9.1 with no way to choose.
# "Camel's Milk (Raw)" maps to 01.1.4.1.4, a real taxonomy leaf that sits
# outside the 257-leaf division-01/02 measurement grid.
_COICOP_MAP: dict[str, str] = {
    "Wheat Grain": "01.1.1.1.1",
    "Rice (100% Broken)": "01.1.1.1.2",
    "Rice (5% Broken)": "01.1.1.1.2",
    "Rice (Long Grain)": "01.1.1.1.2",
    "Rice (Long Grain, Basmati)": "01.1.1.1.2",
    "Rice (Medium Grain)": "01.1.1.1.2",
    "Rice (Medium Grain, Emata)": "01.1.1.1.2",
    "Rice (Milled)": "01.1.1.1.2",
    "Rice (Parboiled)": "01.1.1.1.2",
    "Rice (Short Grain)": "01.1.1.1.2",
    "Sorghum": "01.1.1.1.3",
    "Sorghum (Red)": "01.1.1.1.3",
    "Millet": "01.1.1.1.5",
    "Millet (Pearl)": "01.1.1.1.5",
    "Maize (Corn)": "01.1.1.1.6",
    "Maize Grain (White)": "01.1.1.1.6",
    "Maize Grain (Yellow)": "01.1.1.1.6",
    "Fonio": "01.1.1.1.9",
    "Wheat Flour": "01.1.1.2.1",
    "Sorghum Flour": "01.1.1.2.3",
    "Maize Flour": "01.1.1.2.6",
    "Maize Meal": "01.1.1.2.6",
    "Roller Maize Meal": "01.1.1.2.6",
    "Bread": "01.1.1.3.1",
    "Bread (Traditional)": "01.1.1.3.1",
    "Bread (brown loaf)": "01.1.1.3.1",
    "Bread (small loaf)": "01.1.1.3.1",
    "Bread (white loaf)": "01.1.1.3.1",
    "Bread (fried)": "01.1.1.3.9",  # fried dough cake, not a loaf
    "Goats (Local Quality)": "01.1.2.1.3",
    "Broiler chicken (live)": "01.1.2.1.4",
    "Chicken (live, indigenous breed)": "01.1.2.1.4",
    "Beef (Fresh bovine meat)": "01.1.2.2.1",
    "Goat Meat (Fresh or Chilled)": "01.1.2.2.3",
    "Chicken meat": "01.1.2.2.4",
    "Fish (Dried, Salted, or In Brine)": "01.1.3.2.9",  # preserved, not fresh
    "Cow's Milk (Fresh, Pasteurized)": "01.1.4.1.1",
    "Camel's Milk (Raw)": "01.1.4.1.4",  # off-grid leaf, see note above
    "Sunflower-seed Oil (Refined)": "01.1.5.1.1",
    "Palm Oil (Refined)": "01.1.5.1.2",
    "Refined Vegetable Oil": "01.1.5.1.9",
    "Banana (unspecified)": "01.1.6.1.2",  # dessert banana; cf. Cooking Banana
    "Groundnuts (In Shell)": "01.1.6.8.8",
    "Groundnuts (Shelled)": "01.1.6.8.8",
    "Cabbage (Unspecified)": "01.1.7.1.2",
    "Chomolia": "01.1.7.1.9",  # collard-type leafy green
    "Onions": "01.1.7.4.3",
    "Potato (Irish)": "01.1.7.5.1",
    "Sweet Potatoes": "01.1.7.5.2",
    "Cassava": "01.1.7.5.3",
    "Yams": "01.1.7.5.4",
    "Cooking Banana (unspecified)": "01.1.7.5.7",
    "Beans (Brown)": "01.1.7.6.1",
    "Beans (Sugar)": "01.1.7.6.1",
    "Beans (White)": "01.1.7.6.1",
    "Beans (Yellow)": "01.1.7.6.1",
    "Beans (mixed)": "01.1.7.6.1",
    "Broad Beans": "01.1.7.6.2",
    "Fava bean": "01.1.7.6.2",
    "Cowpeas (Mixed)": "01.1.7.6.6",
    "Cowpeas (Red)": "01.1.7.6.6",
    "Cassava Flour": "01.1.7.9.1",
    "Gari": "01.1.7.9.1",
    "Attiéké": "01.1.7.9.9",  # fermented steamed cassava
    "Refined sugar": "01.1.8.1.1",
    "Salt": "01.1.9.3.1",
}

def _fetch_pages(session, country_code: str, cutoff: date) -> list[dict]:
    rows: list[dict] = []
    url = _API
    params = {
        "country_code": country_code,
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
    unmapped: set[str] = set()
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
        coicop = _COICOP_MAP.get(product)
        if not coicop:
            unmapped.add(product)
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
            "coicop_code": coicop,
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
    if unmapped:
        logger.warning(
            "[%s] no COICOP mapping for %d product(s) -- rows dropped: %s",
            source_key,
            len(unmapped),
            ", ".join(sorted(unmapped)),
        )
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


def fetch_fews_ssd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ssd")


def fetch_fews_bdi(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bdi")


def fetch_fews_som(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="som")
