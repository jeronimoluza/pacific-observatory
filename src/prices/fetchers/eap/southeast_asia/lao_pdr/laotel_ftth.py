"""Lao Telecom — FTTH broadband tariff (Vientiane, JS-rendered plan page).

The plan prices are rendered client-side via JavaScript. A Playwright fetch
is required to get the rendered HTML. The fetcher guards the Playwright import
so the module stays importable on machines without it.

Confirmed plans (2026-06-15, from rendered page):
  35 Mbps → 165,000 LAK/mo, 55 Mbps → 255,000, 70 Mbps → 355,000,
  80 Mbps → 505,000, 100 Mbps → 555,000, 120 Mbps → 755,000,
  160 Mbps → 1,005,000, 170 Mbps → 1,105,000, 180 Mbps → 1,355,000,
  300 Mbps → 2,255,000, 320 Mbps → 3,605,000, 400 Mbps → 4,505,000,
  480 Mbps → 5,405,000.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.laotel.com/la/new-package-ftth.php?Lang=en"
_COUNTRY = "Lao PDR"
_CURRENCY = "LAK"
_SOURCE_KEY = "la_laotel_ftth"
_COICOP = "08.3.0"
_UNIT = "month"

_IDENT = ["source_key", "item_name", "price_local"]

_SPEED_RE = re.compile(r"(\d+)\s*Mbps", re.IGNORECASE)
_PRICE_RE = re.compile(r"([\d,]+)\s*(?:LAK|KIP|kip|lak)?", re.IGNORECASE)

# Hardcoded plan table as fallback when Playwright is unavailable.
# Update this dict when the page is re-probed and plans change.
_KNOWN_PLANS: dict[int, float] = {
    35: 165_000,
    55: 255_000,
    70: 355_000,
    80: 505_000,
    100: 555_000,
    120: 755_000,
    160: 1_005_000,
    170: 1_105_000,
    180: 1_355_000,
    300: 2_255_000,
    320: 3_605_000,
    400: 4_505_000,
    480: 5_405_000,
}


def _build_rows_from_plans(plans: dict[int, float], today: str) -> list[dict]:
    rows: list[dict] = []
    for speed, price in plans.items():
        item_name = f"FTTH {speed} Mbps"
        row: dict = {
            "observation_date": today,
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def _fetch_with_playwright(today: str) -> list[dict]:
    """Attempt a Playwright fetch to get the JS-rendered plan table."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning(
            "Playwright not installed — falling back to _KNOWN_PLANS for laotel_ftth"
        )
        return []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(_URL, wait_until="networkidle", timeout=20_000)
        page.wait_for_timeout(4_000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    plans: dict[int, float] = {}
    for tag in soup.find_all(string=_SPEED_RE):
        container = tag.parent
        for _ in range(6):
            if container is None:
                break
            block = container.get_text(separator=" ", strip=True)
            speed_m = _SPEED_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if speed_m and price_m:
                speed = int(speed_m.group(1))
                try:
                    price = float(price_m.group(1).replace(",", ""))
                except ValueError:
                    break
                if price >= 10_000 and speed not in plans:
                    plans[speed] = price
                break
            container = container.parent

    return _build_rows_from_plans(plans, today) if plans else []


def fetch_la_laotel_ftth(cutoff: date) -> pd.DataFrame | None:
    today = datetime.now(timezone.utc).date().isoformat()
    # Tariff snapshots: emit only if today > cutoff (avoids re-emitting same day)
    if date.fromisoformat(today) <= cutoff:
        return None

    rows = _fetch_with_playwright(today)
    if not rows:
        logger.info(
            "Using _KNOWN_PLANS hardcoded table for laotel_ftth (Playwright unavailable)"
        )
        rows = _build_rows_from_plans(_KNOWN_PLANS, today)

    return pd.DataFrame(rows) if rows else None
