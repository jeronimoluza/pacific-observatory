"""Samoa Water Authority — water/wastewater tariff and fee schedule.

Scrapes the static HTML rates page at samoawaterauthority.ws/our-services/
rates-tariffs/. Each tariff/fee line is a Visual Composer "Ultimate Pricing
Table" widget (`div.ult_pricing_table_wrap`) with a step/plan label (h3), a
consumption-band or fee description (h5), and a price (`<strong>$X.XX</strong>`).
No JS execution required -- the page is plain server-rendered HTML with no
`<table>` elements (pandas.read_html finds none), so extraction goes
through the widget divs directly.

GOTCHA: the page's own headings only separate top-level tariff *types*
("Water Tariff", "Wastewater Tariff", "Water Truck Service Fees",
"Service Disconnection", "NEW ACCOUNT/CONNECTION APPLICATION") -- there is
no textual "Domestic" vs "Commercial" label anywhere in the DOM for the two
back-to-back tiered plans under "Water Tariff" (steps land at $0.61/$1.34/
$1.74/flat-$16 for plan 1, $1.42/$1.82/flat-$25.60 for plan 2). Rather than
fabricate a customer-class label neither confirmed nor denied by the
source, this fetcher numbers them "Plan 1" / "Plan 2" in sequence and
records the raw heading/step text verbatim in `item_name` and `notes`.

Source URL: https://samoawaterauthority.ws/our-services/rates-tariffs/
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://samoawaterauthority.ws/our-services/rates-tariffs/"
_COUNTRY = "Samoa"
_CURRENCY = "WST"
_SOURCE_KEY = "swa_water_tariff"
_COICOP_CODE = "04.4.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"[\d.,]+")
# A new "plan" starts whenever we see "Step 1" again within the same section.
_PLAN_RESTART_LABELS = {"step 1"}


def _section_heading(block, soup: BeautifulSoup) -> str | None:
    for el in block.find_all_previous(["h1", "h2", "h3", "h4"]):
        if el.find_parent("div", class_="ult_pricing_table_wrap"):
            continue
        return el.get_text(strip=True)
    return None


def _extract_tariffs(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    blocks = soup.find_all("div", class_="ult_pricing_table_wrap")

    plan_num = {}  # section -> current plan counter
    last_section = None
    for block in blocks:
        h3 = block.find("h3")
        h5 = block.find("h5")
        price_el = block.find("strong")
        if not h3 or not price_el:
            continue
        step_label = h3.get_text(strip=True)
        band_label = h5.get_text(strip=True) if h5 else ""
        m = _PRICE_RE.search(price_el.get_text(strip=True))
        if not m:
            continue
        price_local = float(m.group(0).replace(",", ""))

        section = _section_heading(block, soup) or "Unlabeled"
        if section != last_section:
            plan_num[section] = 1
            last_section = section
        elif step_label.strip().lower() in _PLAN_RESTART_LABELS:
            plan_num[section] = plan_num.get(section, 1) + 1

        item_name = (
            f"SWA Samoa {section}, Plan {plan_num[section]}, "
            f"{step_label} ({band_label})".strip()
        )
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "cubic meter" if "tariff" in section.lower() else "fee",
            "source_url": _URL,
            "notes": f"section={section}, step={step_label}, band={band_label}",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_swa_water_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = _extract_tariffs(soup, obs_date)
    if not rows:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning(
            "[%s] %d duplicate observation_hash rows before de-dup",
            _SOURCE_KEY,
            dup_count,
        )
        df = df.drop_duplicates(subset="observation_hash")
    return df
