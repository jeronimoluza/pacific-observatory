"""BeninPetro current pump prices with Wayback monthly backfill."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_COUNTRY = "Benin"
_CURRENCY = "XOF"
_SOURCE_KEY = "beninpetro_bj_monthly"
_LIVE_URL = "https://beninpetro.com/"
_CDX_URL = "https://web.archive.org/cdx/search/cdx"
_WAYBACK_URL = "https://web.archive.org/web/{timestamp}id_/{url}"
_PRODUCTS = {
    "essence": "Essence",
    "gasoil": "Gasoil",
    "gaz": "Gaz",
    "petrole lampant": "Pétrole lampant",
    "pétrole lampant": "Pétrole lampant",
    "gaz butane": "Gaz",
}
_PRICE_RE = re.compile(r"(\d[\d\s.,]*)\s*F\s*/\s*(L|KG)\b", re.IGNORECASE)
_THROTTLE_S = 1.0


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _clean_product(value: str) -> str | None:
    key = re.sub(r"\s+", " ", value.strip().lower())
    return _PRODUCTS.get(key)


def _parse_price(value: str) -> float | None:
    text = value.replace(" ", "").replace(",", ".")
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _parse_prices(html: str, obs_date: date) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in soup.get_text("\n").splitlines()
        if re.sub(r"\s+", " ", line).strip()
    ]

    rows: list[dict] = []
    for idx, line in enumerate(lines):
        product = _clean_product(line)
        if product is None:
            continue
        for candidate in lines[idx + 1 : idx + 5]:
            match = _PRICE_RE.search(candidate)
            if not match:
                continue
            price = _parse_price(match.group(1))
            if price is None:
                break
            unit = "kg" if match.group(2).lower() == "kg" else "L"
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": unit,
                    "subnational_area": "national_avg",
                }
            )
            break
    return rows


def _fetch_live(session) -> list[dict]:
    resp = session.get(_LIVE_URL, timeout=45)
    resp.raise_for_status()
    return _parse_prices(resp.text, _month_start(datetime.now(timezone.utc).date()))


def _parse_timestamp(value: str) -> date | None:
    if len(value) < 8:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _is_homepage(original: str) -> bool:
    parsed = urlparse(original)
    path = parsed.path.strip("/")
    return path in {"", "accueil", "home"}


def _discover_wayback(session, cutoff: date) -> list[tuple[str, str]]:
    params = {
        "url": "beninpetro.com",
        "matchType": "domain",
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,statuscode,mimetype",
        "collapse": "timestamp:6",
        "from": cutoff.strftime("%Y%m%d"),
    }
    try:
        resp = session.get(_CDX_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except (json.JSONDecodeError, ValueError, Exception) as exc:
        logger.warning("[beninpetro_bj] Wayback CDX unavailable: %s", exc)
        return []
    if not data or len(data) < 2:
        return []

    out: list[tuple[str, str]] = []
    seen_months: set[str] = set()
    for row in data[1:]:
        if len(row) < 2:
            continue
        timestamp, original = row[0], row[1]
        snap_date = _parse_timestamp(timestamp)
        if snap_date is None or snap_date <= cutoff:
            continue
        if not _is_homepage(original):
            continue
        month_key = timestamp[:6]
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        out.append((timestamp, original))
    return out


def _fetch_wayback_rows(session, cutoff: date) -> list[dict]:
    rows: list[dict] = []
    for idx, (timestamp, original) in enumerate(_discover_wayback(session, cutoff)):
        if idx > 0:
            time.sleep(_THROTTLE_S)
        snap_date = _parse_timestamp(timestamp)
        if snap_date is None:
            continue
        url = _WAYBACK_URL.format(timestamp=timestamp, url=original)
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "[beninpetro_bj] Wayback snapshot failed %s: %s", timestamp, exc
            )
            continue
        rows.extend(_parse_prices(resp.text, _month_start(snap_date)))
    return rows


def fetch_beninpetro_bj(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []

    try:
        rows.extend(_fetch_live(session))
    except Exception as exc:
        logger.warning("[beninpetro_bj] live fetch failed: %s", exc)

    rows.extend(_fetch_wayback_rows(session, cutoff))
    if not rows:
        return None

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(
        subset=["observation_date", "fuel_product", "subnational_area"],
        keep="last",
    )
    return df.sort_values(["observation_date", "fuel_product"]).reset_index(drop=True)


__all__ = ["fetch_beninpetro_bj"]
