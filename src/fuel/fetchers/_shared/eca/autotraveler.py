"""Autotraveler.ru fetcher — full historical series via per-country JSON feed.

Scraping strategy:
  1. GET /en/{slug}/trend-price-fuel-{slug}.html
     Parse Highstock init JS to discover which JSON column maps to which
     fuel product (chart_92 → Regular 92, chart_95 → Super 95, chart_98 →
     Premium 98, chart_diz → Diesel, chart_lpg → LPG; `_eu` variants hold
     EUR-denominated prices).
  2. GET /stock/stock_{cc}.php
     Returns [[unix_ts, local_fuel_prices..., eur_fuel_prices...], ...],
     covering ~2011-08 to present (per-country cadence varies: daily for
     UA/PL/RU, weekly for smaller markets).
  3. Emit one row per (date × fuel) in the country's declared currency.
     Zero prices (missing source data) are skipped.
"""

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup  # noqa: F401 — kept for symmetry; not strictly needed
from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://autotraveler.ru"

_PRODUCT_LABELS = {
    "chart_92": "Regular 92",
    "chart_95": "Super 95",
    "chart_98": "Premium 98",
    "chart_diz": "Diesel",
    "chart_lpg": "LPG",
}

_PUSH_RE = re.compile(r"(chart_\w+)\.push\(\s*\[(.*?)\]\s*\)\s*;", re.DOTALL)
_DATA_IDX_RE = re.compile(r"data\[i\]\[(\d+)\]")

_COUNTRIES: dict[str, dict] = {
    "ua": {"name": "Ukraine",           "iso3": "UKR", "currency": "UAH", "slug": "ukraine",    "source_key": "autotraveler_ua_daily", "unit": "L"},
    "by": {"name": "Belarus",           "iso3": "BLR", "currency": "BYN", "slug": "belarus",    "source_key": "autotraveler_by_daily", "unit": "L"},
    "md": {"name": "Moldova",           "iso3": "MDA", "currency": "MDL", "slug": "moldova",    "source_key": "autotraveler_md_daily", "unit": "L"},
    "ru": {"name": "Russian Federation", "iso3": "RUS", "currency": "RUB", "slug": "russia",     "source_key": "autotraveler_ru_daily", "unit": "L"},
    "am": {"name": "Armenia",           "iso3": "ARM", "currency": "AMD", "slug": "armenia",    "source_key": "autotraveler_am_daily", "unit": "L"},
    "az": {"name": "Azerbaijan",        "iso3": "AZE", "currency": "AZN", "slug": "azerbaijan", "source_key": "autotraveler_az_daily", "unit": "L"},
    "ge": {"name": "Georgia",           "iso3": "GEO", "currency": "GEL", "slug": "georgia",    "source_key": "autotraveler_ge_daily", "unit": "L"},
    "tr": {"name": "Türkiye",           "iso3": "TUR", "currency": "TRY", "slug": "turkey",     "source_key": "autotraveler_tr_daily", "unit": "L"},
    "al": {"name": "Albania",           "iso3": "ALB", "currency": "ALL", "slug": "albania",    "source_key": "autotraveler_al_daily", "unit": "L"},
    "me": {"name": "Montenegro",        "iso3": "MNE", "currency": "EUR", "slug": "montenegro", "source_key": "autotraveler_me_daily", "unit": "L"},
    "mk": {"name": "North Macedonia",   "iso3": "MKD", "currency": "MKD", "slug": "macedonia",  "source_key": "autotraveler_mk_daily", "unit": "L"},
    "rs": {"name": "Serbia",            "iso3": "SRB", "currency": "RSD", "slug": "serbia",     "source_key": "autotraveler_rs_daily", "unit": "L"},
    "bg": {"name": "Bulgaria",          "iso3": "BGR", "currency": "BGN", "slug": "bulgaria",   "source_key": "autotraveler_bg_daily", "unit": "L"},
    "hr": {"name": "Croatia",           "iso3": "HRV", "currency": "EUR", "slug": "croatia",    "source_key": "autotraveler_hr_daily", "unit": "L"},
    "pl": {"name": "Poland",            "iso3": "POL", "currency": "PLN", "slug": "poland",     "source_key": "autotraveler_pl_daily", "unit": "L"},
    "ro": {"name": "Romania",           "iso3": "ROU", "currency": "RON", "slug": "romania",    "source_key": "autotraveler_ro_daily", "unit": "L"},
}


def _discover_columns(html: str, want_eur: bool) -> dict[int, str]:
    """Return {json_col_index: product_label} for the requested currency view."""
    mapping: dict[int, str] = {}
    for match in _PUSH_RE.finditer(html):
        var_name = match.group(1)
        is_eur = var_name.endswith("_eu")
        if is_eur != want_eur:
            continue
        base = var_name[:-3] if is_eur else var_name
        label = _PRODUCT_LABELS.get(base)
        if label is None:
            continue
        indices = _DATA_IDX_RE.findall(match.group(2))
        if len(indices) < 2:
            continue
        # The second data[i][N] reference (first is always [0] = timestamp)
        try:
            col = int(indices[1])
        except ValueError:
            continue
        mapping[col] = label
    return mapping


def _scrape_country(cc: str, meta: dict, cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    slug = meta["slug"]
    page_url = f"{_BASE_URL}/en/{slug}/trend-price-fuel-{slug}.html"
    json_url = f"{_BASE_URL}/stock/stock_{cc}.php"

    page_resp = session.get(page_url, timeout=30)
    page_resp.raise_for_status()

    want_eur = meta["currency"] == "EUR"
    col_map = _discover_columns(page_resp.text, want_eur=want_eur)
    if not col_map:
        logger.warning(
            "[autotraveler_%s] No %s columns discovered on %s",
            cc,
            "EUR" if want_eur else "local",
            page_url,
        )
        return None

    json_resp = session.get(json_url, headers={"Referer": page_url}, timeout=60)
    json_resp.raise_for_status()
    try:
        rows_json = json_resp.json()
    except ValueError:
        logger.exception("[autotraveler_%s] Bad JSON from %s", cc, json_url)
        return None

    rows_out: list[dict] = []
    for entry in rows_json:
        if not entry or len(entry) < 2:
            continue
        try:
            ts = int(entry[0])
        except (TypeError, ValueError):
            continue
        obs = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        if obs <= cutoff:
            continue
        iso = obs.strftime("%Y-%m-%d")
        for col, label in col_map.items():
            if col >= len(entry):
                continue
            val = entry[col]
            try:
                price = float(val)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            rows_out.append(
                {
                    "observation_date": iso,
                    "country": meta["name"],
                    "fuel_product": label,
                    "price_local": price,
                    "currency": meta["currency"],
                    "unit": meta["unit"],
                    "source_key": meta["source_key"],
                }
            )

    if not rows_out:
        logger.info("[autotraveler_%s] No rows after cutoff %s", cc, cutoff)
        return None

    df = pd.DataFrame(rows_out)
    df = df.sort_values(["observation_date", "fuel_product"]).reset_index(drop=True)
    logger.info("[autotraveler_%s] %d rows (%s → %s)", cc, len(df), df["observation_date"].iloc[0], df["observation_date"].iloc[-1])
    return df


def _make_fetcher(cc: str):
    meta = _COUNTRIES[cc]

    def _fetch(cutoff: date) -> pd.DataFrame | None:
        return _scrape_country(cc, meta, cutoff)

    _fetch.__name__ = f"fetch_autotraveler_{cc}"
    _fetch.__doc__ = f"Fetch fuel price history for {meta['name']} from autotraveler.ru."
    return _fetch


fetch_autotraveler_ua = _make_fetcher("ua")
fetch_autotraveler_by = _make_fetcher("by")
fetch_autotraveler_md = _make_fetcher("md")
fetch_autotraveler_ru = _make_fetcher("ru")
fetch_autotraveler_am = _make_fetcher("am")
fetch_autotraveler_az = _make_fetcher("az")
fetch_autotraveler_ge = _make_fetcher("ge")
fetch_autotraveler_tr = _make_fetcher("tr")
fetch_autotraveler_al = _make_fetcher("al")
fetch_autotraveler_me = _make_fetcher("me")
fetch_autotraveler_mk = _make_fetcher("mk")
fetch_autotraveler_rs = _make_fetcher("rs")
fetch_autotraveler_bg = _make_fetcher("bg")
fetch_autotraveler_hr = _make_fetcher("hr")
fetch_autotraveler_pl = _make_fetcher("pl")
fetch_autotraveler_ro = _make_fetcher("ro")
