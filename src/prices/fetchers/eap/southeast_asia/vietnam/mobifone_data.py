"""MobiFone Vietnam mobile data and bundle tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Vietnam"
_CURRENCY = "VND"
_SOURCE_KEY = "vn_mobifone_data"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]
_URL = "https://5g.mobifone.vn/dich-vu-di-dong/goi-data?target=Data"

_PRICE_RE = re.compile(r"^([0-9][0-9.]*)\s*đ\s*/\s*(.+)$", re.I)
_NON_NAME_LINES = {
    "FREE",
    "HOT",
    "Đăng ký",
    "Data:",
    "Thoại nội mạng:",
    "Thoại liên mạng:",
    "SMS nội mạng:",
    "🔥 5G 🔥",
}


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _price_and_validity(raw: str) -> tuple[float, str] | None:
    m = _PRICE_RE.match(raw)
    if not m:
        return None
    return float(m.group(1).replace(".", "")), m.group(2).strip()


def _plan_name(previous: list[str]) -> str | None:
    for line in reversed(previous):
        if line not in _NON_NAME_LINES and not re.match(r"^[0-9.]+\s*GB$", line, re.I):
            return line
    return None


def _notes_after(lines: list[str], price_index: int, validity: str) -> str:
    parts = [f"Validity {validity}"]
    for line in lines[price_index + 1 : min(len(lines), price_index + 8)]:
        if line == "Đăng ký":
            break
        parts.append(line)
    return "; ".join(parts)


def _extract_packages(lines: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for i, line in enumerate(lines):
        parsed = _price_and_validity(line)
        if parsed is None:
            continue
        price, validity = parsed
        if price <= 0:
            continue
        item_name = _plan_name(lines[max(0, i - 4) : i])
        if not item_name:
            continue
        rows.append((item_name, price, _notes_after(lines, i, validity)))
    return rows


def fetch_vn_mobifone_data(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    resp = get_session().get(_URL, timeout=60)
    resp.raise_for_status()

    rows: list[dict] = []
    seen: set[tuple[str, float, str]] = set()
    ts = get_scrape_ts()
    for item_name, price, notes in _extract_packages(_lines(resp.text)):
        key = (item_name.lower(), price, notes.lower())
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
