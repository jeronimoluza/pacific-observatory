"""FSM Telecommunications Corporation (FSMTC) -- published tariff schedules.

FSMTC's site (fsmtc.fm) renders its ADSL, Kaboom (wireless internet), and
Pacifica TV / MyTV Kosrae cable rates as static HTML tables (no JS, no API) --
Tier 1A, server-rendered, plain ``requests`` needs no browser impersonation.

Three pages are combined into one source because they are the same tenant
publishing the same shape of thing (a residential/business service-tier
tariff table), per the onboarding skill's "narrow source" guidance -- COICOP
08.3.0 (telephone & internet services) covers all three:

- ``/internet/adsl`` -- ADSL home/business tiers. Pohnpei, Chuuk and Yap
  share one "NEW" rate table (they're fibre-linked); Kosrae has its own,
  separately-priced table (site explicitly says Kosrae awaits the same
  rollout). Each tier has a "with line rental" and "without line rental"
  price -- both are genuine distinct tariff line items, emitted separately.
- ``/internet/dialup-rates`` -- despite the URL, this is the *Kaboom* fixed
  wireless internet price table (Bronze/Silver/Gold/Sapphire/Diamond), not
  legacy dial-up. FSM-wide, no per-state breakdown published.
- ``/cable/rates-info`` -- Pacifica TV (Pohnpei/Chuuk/Yap) is a table;
  MyTV Kosrae's rates are only published as prose sentences on the same
  page, not a table -- regex-extracted here.

No effective-date is published anywhere on these pages (unlike Vanuatu's
URA tariff, which prints one per row) -- these are "current rate" pages that
get edited in place when FSMTC changes a price. Modelled as a daily
``period_kind: snapshot`` at the scrape date, gated so the fetcher only
re-emits once cutoff has moved past today (same pattern as
``eap/east_asia/south_korea/price_go_kr.py``). A silent price change between
runs is picked up as a new observation_date row with a different price the
next time this fetcher runs -- there is no staleness risk requiring a
tripwire because every run re-reads the live page, it never hardcodes a
table.

Currency is USD (FSM's actual currency -- no FX conversion needed).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_fsmtc_tariff"
_COICOP = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_ADSL_URL = "https://www.fsmtc.fm/internet/adsl"
_KABOOM_URL = "https://www.fsmtc.fm/internet/dialup-rates"
_CABLE_URL = "https://www.fsmtc.fm/cable/rates-info"

_PCY = "Pohnpei/Chuuk/Yap"  # fibre-linked states sharing one ADSL rate card


def _price(text: str) -> float | None:
    # rstrip a trailing sentence period -- the prose regexes on the MyTV
    # Kosrae section capture "25.00." (the sentence's full stop) because
    # "." is also a thousands/decimal-point character we want to keep
    # mid-number.
    text = text.replace("$", "").replace(",", "").strip().rstrip(".")
    try:
        val = float(text)
    except ValueError:
        return None
    return val if val > 0 else None


def _parse_two_col_table(table, label_prefix: str, subnational_area: str) -> list[dict]:
    """A tier-name row + two price columns (with-line / without-line)."""
    trs = table.find_all("tr")
    if not trs:
        return []
    header_cells = [c.get_text(" ", strip=True) for c in trs[0].find_all("td")]
    col_names = header_cells[1:] if len(header_cells) > 1 else ["", ""]
    out = []
    for tr in trs[1:]:
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        tier = cells[0].get_text(" ", strip=True)
        if not tier:
            continue
        for i, cell in enumerate(cells[1:]):
            price = _price(cell.get_text(" ", strip=True))
            if price is None:
                continue
            variant = col_names[i] if i < len(col_names) else f"col{i}"
            variant = re.sub(r"\s+MRC$", "", variant, flags=re.I).strip()
            item_name = (
                f"{label_prefix} {tier} ({variant})"
                if variant
                else f"{label_prefix} {tier}"
            )
            out.append(
                {
                    "item_name": item_name,
                    "price_local": price,
                    "subnational_area": subnational_area,
                    "unit": "month",
                }
            )
    return out


def _parse_kosrae_adsl_table(table) -> list[dict]:
    """One MRC column, with a 'BUSINESS ADSL' sub-header row mid-table."""
    out = []
    section = "Home ADSL"
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue
        label = cells[0].get_text(" ", strip=True)
        price_text = cells[1].get_text(" ", strip=True)
        if label.upper() in ("HOME ADSL", "BUSINESS ADSL"):
            section = "Business ADSL" if "BUSINESS" in label.upper() else "Home ADSL"
            continue
        price = _price(price_text)
        if price is None or not label:
            continue
        out.append(
            {
                "item_name": f"Kosrae ADSL {section} -- {label}",
                "price_local": price,
                "subnational_area": "Kosrae",
                "unit": "month",
            }
        )
    return out


def _parse_adsl(session) -> list[dict]:
    resp = session.get(_ADSL_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    tables = soup.find_all("table")
    if len(tables) < 3:
        logger.warning(
            "[%s] expected >=3 ADSL tables, found %d", _SOURCE_KEY, len(tables)
        )
        return []

    rows = _parse_two_col_table(tables[0], f"ADSL Home Net ({_PCY})", _PCY)
    rows += _parse_two_col_table(tables[1], f"ADSL Business Net ({_PCY})", _PCY)
    rows += _parse_kosrae_adsl_table(tables[2])
    for r in rows:
        r["source_url"] = _ADSL_URL
    return rows


def _parse_kaboom(session) -> list[dict]:
    resp = session.get(_KABOOM_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if table is None:
        logger.warning("[%s] no Kaboom table found", _SOURCE_KEY)
        return []
    out = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 4:
            continue
        package, down, up, mrc = cells[0], cells[1], cells[2], cells[3]
        price = _price(mrc)
        if price is None or not package:
            continue
        out.append(
            {
                "item_name": f"Kaboom {package} ({down} down / {up} up)",
                "price_local": price,
                "subnational_area": None,
                "unit": "month",
                "source_url": _KABOOM_URL,
            }
        )
    return out


def _parse_cable(session) -> list[dict]:
    resp = session.get(_CABLE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    out = []

    table = soup.find("table")
    if table is not None:
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != 2:
                continue
            label = cells[0].get_text(" ", strip=True)
            price = _price(cells[1].get_text(" ", strip=True))
            if price is None or not label:
                continue
            out.append(
                {
                    "item_name": f"Pacifica TV ({_PCY}) -- {label}",
                    "price_local": price,
                    "subnational_area": _PCY,
                    "unit": "month",
                    "source_url": _CABLE_URL,
                }
            )
    else:
        logger.warning("[%s] no Pacifica TV table found", _SOURCE_KEY)

    # MyTV Kosrae is prose, not a table -- pull the four "$X.XX"-anchored
    # sentences under the "MyTV Kosrae" heading.
    text = soup.get_text(" ", strip=True)
    # The FIRST "MyTV Kosrae" hit is a nav-menu link at the top of the page;
    # the actual rates section is the LAST occurrence.
    i = text.rfind("MyTV Kosrae")
    if i == -1:
        logger.warning("[%s] MyTV Kosrae section not found", _SOURCE_KEY)
        return out
    block = text[i : i + 800]
    patterns = [
        (
            r"Installation \(one time fee\) of\s*\$\s*([\d,.]+)",
            "Installation fee (one-time)",
            "one-time",
        ),
        (
            r"Monthly recurring charge of\s*\$\s*([\d,.]+)",
            "Monthly recurring charge",
            "month",
        ),
        (r"Additional TV charge is\s*\$\s*([\d,.]+)", "Additional TV charge", "month"),
        (r"Reconnection fee of\s*\$\s*([\d,.]+)", "Reconnection fee", "one-time"),
    ]
    for pattern, label, unit in patterns:
        m = re.search(pattern, block, re.I)
        if not m:
            continue
        price = _price(m.group(1))
        if price is None:
            continue
        out.append(
            {
                "item_name": f"MyTV Kosrae -- {label}",
                "price_local": price,
                "subnational_area": "Kosrae",
                "unit": unit,
                "source_url": _CABLE_URL,
            }
        )
    return out


def fetch_fm_fsmtc_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    parsed: list[dict] = []
    parsed += _parse_adsl(session)
    parsed += _parse_kaboom(session)
    parsed += _parse_cable(session)

    if not parsed:
        logger.warning("[%s] no tariff rows parsed from any page", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": item.get("subnational_area"),
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item.get("unit"),
            "source_url": item["source_url"],
            "notes": None,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
