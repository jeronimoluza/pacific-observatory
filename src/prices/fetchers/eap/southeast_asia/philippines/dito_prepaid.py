"""DITO Philippines prepaid data, 5G, app, and starter-pack tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Philippines"
_CURRENCY = "PHP"
_SOURCE_KEY = "ph_dito_prepaid"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]
_URL = "https://dito.ph/prepaid"

_PRICE_RE = re.compile(r"^(?:₱|P)\s*([0-9][0-9,.]*)$")
_PLAN_TOKEN_RE = re.compile(
    r"(?:MAXX|STREAMZONE|GAMEZONE|LEVEL-UP|SOCIALS|UNLI5G|UNLI 5G|APP BOOSTER|DATA\s*\d+)",
    re.I,
)
_SECTION_HEADINGS = {
    "DATA",
    "UNLI5G",
    "UNLI 5G",
    "STREAMZONE",
    "GAMEZONE",
    "LEVEL-UP",
    "APP BOOSTER",
}


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _price(raw: str) -> float | None:
    m = _PRICE_RE.match(raw)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _plan_name(previous: list[str]) -> str | None:
    for j in range(len(previous) - 1, -1, -1):
        line = previous[j]
        if line in _SECTION_HEADINGS and j + 1 < len(previous):
            return f"{line} {previous[j + 1]}".replace("\xa0", " ")
        if _PLAN_TOKEN_RE.search(line):
            if j > 0 and previous[j - 1] in {"DATA", "UNLI5G", "UNLI 5G"}:
                return f"{previous[j - 1]} {line}".replace("\xa0", " ")
            return line.replace("\xa0", " ")
    return None


def _extract_packages(lines: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for i, line in enumerate(lines):
        price = _price(line)
        if price is None:
            continue
        previous = lines[max(0, i - 8) : i]
        item_name = _plan_name(previous)
        if not item_name:
            continue
        notes = "; ".join(previous[-5:] + [line] + lines[i + 1 : min(len(lines), i + 3)])
        rows.append((item_name, price, notes))
    return rows


def fetch_ph_dito_prepaid(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    resp = get_session().get(_URL, timeout=60)
    resp.raise_for_status()

    rows: list[dict] = []
    seen: set[tuple[str, float]] = set()
    ts = get_scrape_ts()
    for item_name, price, notes in _extract_packages(_lines(resp.text)):
        key = (item_name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name[:500],
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": notes[:500],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
