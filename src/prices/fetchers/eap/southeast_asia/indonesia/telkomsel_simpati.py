"""Telkomsel Indonesia SIMPATI prepaid package tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Indonesia"
_CURRENCY = "IDR"
_SOURCE_KEY = "id_telkomsel_simpati"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]
_URL = "https://www.telkomsel.com/en/simpati"

_PRICE_RE = re.compile(r"^Rp\s*([0-9][0-9.]*)$")
_QUOTA_RE = re.compile(r"^[0-9.]+\s*(?:GB|MB)$", re.I)
_DURATION_RE = re.compile(r"^[0-9]+\s*(?:day|days|month|months)$", re.I)
_GENERIC_LINES = {
    "Purchase",
    "See all packages",
    "Choose the package and number you prefer",
    "Various payment methods",
}


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _price(raw: str) -> float | None:
    m = _PRICE_RE.match(raw)
    if not m:
        return None
    return float(m.group(1).replace(".", ""))


def _is_plan_name(line: str) -> bool:
    if line in _GENERIC_LINES:
        return False
    if line.startswith("Validity ") or line.startswith("Extra "):
        return False
    if _QUOTA_RE.match(line) or _DURATION_RE.match(line):
        return False
    if "Rp" in line:
        return False
    return any(ch.isalpha() for ch in line)


def _with_spec(item_name: str, context: list[str]) -> str:
    quota = next(
        (
            part.replace("Extra ", "")
            for part in reversed(context)
            if _QUOTA_RE.match(part) or part.startswith("Extra ")
        ),
        None,
    )
    validity = next(
        (part.replace("Validity ", "") for part in reversed(context) if part.startswith("Validity ")),
        None,
    )
    if not validity:
        validity = next((part for part in reversed(context) if _DURATION_RE.match(part)), None)
    spec = " - ".join(part for part in (quota, validity) if part)
    return f"{item_name} - {spec}" if spec else item_name


def _extract_packages(lines: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for i, line in enumerate(lines):
        price = _price(line)
        if price is None:
            continue
        context = lines[max(0, i - 5) : i]
        candidates = [part for part in context if _is_plan_name(part)]
        if not candidates:
            continue
        item_name = _with_spec(candidates[-1], context)
        notes = "; ".join(context[-3:] + [line])
        rows.append((item_name, price, notes))
    return rows


def fetch_id_telkomsel_simpati(cutoff: date) -> pd.DataFrame | None:
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
