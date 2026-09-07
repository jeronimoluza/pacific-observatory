"""M1 Singapore prepaid data-pack and top-up tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_m1_prepaid"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]

_DATA_PACKS_URL = "https://www.m1.com.sg/mobile/prepaid-plans/m-card/data-packs"
_TOP_UP_URL = "https://www.m1.com.sg/mobile/prepaid-plans/m-card/top-up"

_PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{2})?)")


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _price(raw: str) -> float | None:
    m = _PRICE_RE.search(raw)
    return float(m.group(1)) if m else None


def _extract_data_packs(lines: list[str]) -> list[tuple[str, float, str, str]]:
    rows = []
    for i, line in enumerate(lines):
        if not line.endswith("Data Pack") or i + 1 >= len(lines):
            continue
        price = _price(lines[i + 1])
        if price is None:
            continue
        notes = "; ".join(lines[i + 1 : min(i + 5, len(lines))])
        rows.append((line, price, notes, _DATA_PACKS_URL))
    return rows


def _extract_topups(lines: list[str]) -> list[tuple[str, float, str, str]]:
    rows = []
    marker = "M1 all-in-1 5G top up"
    start = lines.index(marker) if marker in lines else 0
    stop = (
        lines.index("Where can I top up?")
        if "Where can I top up?" in lines
        else len(lines)
    )
    section = lines[start:stop]
    for i, line in enumerate(section):
        price = _price(line)
        if price is None:
            continue
        is_plan = (
            "Top Up" in line
            or line.startswith("Power $")
            or line.startswith("Super$")
            or (
                line.startswith("$")
                and i + 1 < len(section)
                and "Main Balance" in section[i + 1]
            )
        )
        if not is_plan:
            continue
        name = (
            line
            if not line.startswith("$") or "Top Up" in line
            else f"Main balance top-up {line}"
        )
        notes = "; ".join(section[i + 1 : min(i + 7, len(section))])
        rows.append((name, price, notes, _TOP_UP_URL))
    return rows


def fetch_sg_m1_prepaid(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    data_resp = session.get(_DATA_PACKS_URL, timeout=45)
    data_resp.raise_for_status()
    topup_resp = session.get(_TOP_UP_URL, timeout=45)
    topup_resp.raise_for_status()

    plan_rows = _extract_data_packs(_lines(data_resp.text))
    plan_rows.extend(_extract_topups(_lines(topup_resp.text)))

    rows: list[dict] = []
    seen: set[str] = set()
    ts = get_scrape_ts()
    for item_name, price, notes, source_url in plan_rows:
        key = item_name.lower()
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
            "source_url": source_url,
            "notes": notes[:500],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
