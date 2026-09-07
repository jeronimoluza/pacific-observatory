"""Lao Telecom mobile package tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
import urllib3

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.laotel.com/la/shop-LTC-buy-package.php?Lang=en"
_COUNTRY = "Lao PDR"
_CURRENCY = "LAK"
_SOURCE_KEY = "la_laotel_mobile_packages"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]

_GROUP_RE = re.compile(
    r'\{\s*nameTabs:\s*"(?P<group>[^"]+)",\s*img:\s*\[(?P<body>.*?)\]\s*\}',
    re.DOTALL,
)
_ITEM_RE = re.compile(
    r'\{\s*name:\s*"(?P<name>[^"]+)",\s*price:\s*(?P<price>\d+),\s*dial:\s*"(?P<dial>[^"]+)"\s*\}',
    re.DOTALL,
)


def _label_from_group(raw: str) -> str:
    label = raw.removesuffix("Box")
    label = re.sub(r"([a-z])([A-Z])", r"\1 \2", label)
    return label.lower()


def _label_from_image(raw: str) -> str:
    label = re.sub(r"\.(?:png|jpg|jpeg|webp)$", "", raw, flags=re.IGNORECASE)
    label = re.sub(r"[_-]+", " ", label)
    label = re.sub(r"\s+", " ", label)
    return label.strip()


def _extract_packages(html: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    for group_match in _GROUP_RE.finditer(html):
        group = _label_from_group(group_match.group("group"))
        for item_match in _ITEM_RE.finditer(group_match.group("body")):
            name = _label_from_image(item_match.group("name"))
            price = int(item_match.group("price"))
            dial = item_match.group("dial")
            key = (group, dial, price)
            if not name or price <= 0 or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "package_group": group,
                    "item_name": f"{group}: {name}",
                    "price_local": float(price),
                    "dial": dial,
                }
            )
    return rows


def fetch_la_laotel_mobile_packages(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = session.get(_URL, timeout=45, verify=False)
    resp.raise_for_status()

    packages = _extract_packages(resp.text)
    if len(packages) < 5:
        logger.warning("[%s] only %d tariff packages parsed", _SOURCE_KEY, len(packages))

    ts = get_scrape_ts()
    rows: list[dict] = []
    for package in packages:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": package["item_name"],
            "price_local": package["price_local"],
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": f"Official Lao Telecom mobile package; dial {package['dial']}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
