"""SeyPEC Seychelles — embedded Google-Charts history + live snapshot.

Seychelles Petroleum Company (SeyPEC) publishes current retail prices at
``https://www.seypec.com/fuel-prices``. The page also embeds the **full
biweekly history since 2020** as a JSON ``data-chart`` attribute on the
Google-Charts block. That single attribute carries ~200 (date, gasoline,
gasoil, lpg) tuples — the canonical historical source. Kerosene is not in
the chart (price has been flat for years) and is read from the live
"Last modified" snapshot.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import time
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_HISTORY_URL = (
    "https://www.seypec.com/fuel-prices"
    "?created%5Bmin%5D=2020-01-01&created%5Bmax%5D=2099-12-31"
)
_LIVE_URL = "https://www.seypec.com/fuel-prices"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?"
    "url=seypec.com/fuel-prices&output=json&"
    "fl=timestamp,statuscode&filter=statuscode:200"
)
_WAYBACK_FMT = "https://web.archive.org/web/{ts}id_/https://www.seypec.com/fuel-prices"
_COUNTRY = "Seychelles"
_CURRENCY = "SCR"
_SOURCE_KEY = "seypec_sc_monthly"
_THROTTLE_S = 1.0

# "GASOLINE SCR22.68/L"  /  "KEROSENE SCR150.00/5L"  /  "LPG SCR17.50/KG"
_PRICE_RE = re.compile(
    r"(GASOLINE|GASOIL|KEROSENE|LPG)\s*SCR\s*([0-9]+(?:\.[0-9]+)?)\s*/?\s*(5?L|KG)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"Last\s*modified\s*([0-3]?\d)/([01]?\d)/(20\d{2})", re.I)


def _clean_text(html: str) -> str:
    h = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    h = re.sub(r"<style[^>]*>.*?</style>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


def _parse(html: str) -> tuple[date | None, list[tuple[str, float, str]]]:
    text = _clean_text(html)
    m = _DATE_RE.search(text)
    if not m:
        return None, []
    try:
        obs_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None, []
    products: dict[str, tuple[float, str]] = {}
    for pmatch in _PRICE_RE.finditer(text):
        product = pmatch.group(1).capitalize()
        if product == "Lpg":
            product = "LPG"
        price = float(pmatch.group(2))
        unit_raw = pmatch.group(3).upper()
        if unit_raw == "5L":
            price = round(price / 5.0, 4)
            unit = "L"
        elif unit_raw == "KG":
            unit = "kg"
        else:
            unit = "L"
        products.setdefault(product, (price, unit))
    return obs_date, [(p, v, u) for p, (v, u) in products.items()]


_CHART_RE = re.compile(r'data-chart="((?:[^"\\]|\\.)*?)"')

_CHART_PRODUCT_MAP = {
    "GASOLINE": ("Gasoline", "L"),
    "GASOIL": ("Gasoil", "L"),
    "LPG": ("LPG", "kg"),
}


def _parse_chart(page_html: str) -> list[tuple[date, str, float, str]]:
    m = _CHART_RE.search(page_html)
    if not m:
        return []
    try:
        rows = json.loads(html_lib.unescape(m.group(1)))
    except json.JSONDecodeError:
        logger.exception("[seypec_sc] data-chart JSON decode failed")
        return []
    if not rows or not isinstance(rows[0], list):
        return []
    header = [str(h).strip().upper() for h in rows[0]]
    col_map: list[tuple[int, str, str]] = []
    for idx, label in enumerate(header[1:], start=1):
        for keyword, (product, unit) in _CHART_PRODUCT_MAP.items():
            if keyword in label:
                col_map.append((idx, product, unit))
                break
    out: list[tuple[date, str, float, str]] = []
    for row in rows[1:]:
        if not row or len(row) < 2:
            continue
        try:
            obs_date = date.fromisoformat(str(row[0]))
        except ValueError:
            continue
        for idx, product, unit in col_map:
            if idx >= len(row):
                continue
            val = row[idx]
            if val is None:
                continue
            try:
                price = float(val)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            out.append((obs_date, product, round(price, 4), unit))
    return out


def _list_snapshots(session, fallback: date) -> list[str]:
    from_ts = fallback.strftime("%Y%m%d")
    to_ts = date.today().strftime("%Y%m%d")
    url = f"{_CDX_URL}&from={from_ts}&to={to_ts}"
    try:
        resp = session.get(url, timeout=60)
    except Exception:
        logger.exception("[seypec_sc] CDX fetch failed")
        return []
    if resp.status_code != 200:
        logger.warning("[seypec_sc] CDX HTTP %d", resp.status_code)
        return []
    try:
        data = resp.json()
    except Exception:
        logger.exception("[seypec_sc] CDX JSON decode failed")
        return []
    return [row[0] for row in data[1:]] if len(data) > 1 else []


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=60)
    except Exception:
        logger.exception("[seypec_sc] GET %s failed", url)
        return None
    if resp.status_code != 200:
        logger.warning("[seypec_sc] HTTP %d for %s", resp.status_code, url)
        return None
    return resp.text


def _row_for(obs_date: date, product: str, price: float, unit: str) -> dict:
    return {
        "observation_date": obs_date.isoformat(),
        "country": _COUNTRY,
        "fuel_product": product,
        "price_local": price,
        "currency": _CURRENCY,
        "unit": unit,
        "source_key": _SOURCE_KEY,
    }


def fetch_seypec_sc(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []

    history_html = _fetch_html(session, _HISTORY_URL)
    if history_html:
        for obs_date, product, price, unit in _parse_chart(history_html):
            if obs_date <= cutoff:
                continue
            rows.append(_row_for(obs_date, product, price, unit))
        logger.info("[seypec_sc] data-chart → %d rows after cutoff", len(rows))

    live_html = history_html if history_html else _fetch_html(session, _LIVE_URL)
    if live_html:
        obs_date, products = _parse(live_html)
        if obs_date and obs_date > cutoff:
            for product, price, unit in products:
                rows.append(_row_for(obs_date, product, price, unit))
            logger.info(
                "[seypec_sc] live snapshot %s → %d products", obs_date, len(products)
            )

    # Wayback backfill — adds Kerosene history (chart series omits Kerosene).
    for ts in _list_snapshots(session, cutoff):
        time.sleep(_THROTTLE_S)
        wb_html = _fetch_html(session, _WAYBACK_FMT.format(ts=ts))
        if not wb_html:
            continue
        obs_date, products = _parse(wb_html)
        if not obs_date or obs_date <= cutoff:
            continue
        for product, price, unit in products:
            if product != "Kerosene":
                continue
            rows.append(_row_for(obs_date, product, price, unit))

    if not rows:
        logger.info("[seypec_sc] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[seypec_sc] %d rows (%s → %s, %d dates × %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_seypec_sc"]
