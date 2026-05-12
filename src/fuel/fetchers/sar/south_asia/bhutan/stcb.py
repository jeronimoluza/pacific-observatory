"""State Trading Corp of Bhutan retail page (live + Wayback).

STCB doesn't use HTML tables — the page renders prices as flat text,
one block per Fuel Retail Outlet (FRO):

    Date: 2026-05-01
    Ramtokto FRO (Thimphu) Petrol (MS): Nu.102.28 Diesel (HSD): Nu.98.19
    Mebesa FRO (Chukha) Petrol (MS): Nu.101.90 Diesel (HSD): Nu.97.81
    ...

A single Date header applies to every FRO on the snapshot. Prices are in
Bhutanese Ngultrum (BTN), pegged 1:1 to INR.
"""

import logging
import re
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session
from fuel.fetchers._shared.sar.wayback import iterate_snapshots

logger = logging.getLogger(__name__)

_URL = "https://www.stcb.bt/bhutanpetroleum.php"
_COUNTRY = "Bhutan"
_CURRENCY = "BTN"
_SOURCE_KEY = "stcb_bt_retail"

_DATE_RE = re.compile(r"Date:\s*(\d{4}-\d{2}-\d{2})")
_FRO_RE = re.compile(
    r"([A-Z][A-Za-z]+(?:\s+[A-Za-z]+)*?)\s+FRO"
    r"(?:\s*\(([^)]+)\))?"
    r"\s*Petrol\s*\(MS\):\s*Nu\.\s*(\d+(?:\.\d+)?)"
    r"\s*Diesel\s*\(HSD\):\s*Nu\.\s*(\d+(?:\.\d+)?)"
)


def _parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    date_match = _DATE_RE.search(text)
    if not date_match:
        logger.debug("[stcb_bt] no Date header found")
        return []
    try:
        observation_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return []
    obs_str = observation_date.strftime("%Y-%m-%d")

    rows: list[dict] = []
    for m in _FRO_RE.finditer(text):
        fro_name, region, petrol_str, diesel_str = m.groups()
        location = fro_name.strip()
        dzongkhag = region.strip() if region else ""
        try:
            petrol = float(petrol_str)
            diesel = float(diesel_str)
        except ValueError:
            continue
        if petrol > 0:
            rows.append(
                {
                    "observation_date": obs_str,
                    "country": _COUNTRY,
                    "fuel_product": "Petrol",
                    "price_local": petrol,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                    "city": location,
                    "subnational_area": dzongkhag,
                }
            )
        if diesel > 0:
            rows.append(
                {
                    "observation_date": obs_str,
                    "country": _COUNTRY,
                    "fuel_product": "Diesel",
                    "price_local": diesel,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                    "city": location,
                    "subnational_area": dzongkhag,
                }
            )
    return rows


def _fetch_live() -> list[dict]:
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[stcb_bt] live fetch failed")
        return []
    return _parse(resp.text)


def fetch_bt_stcb(cutoff: date) -> pd.DataFrame | None:
    """Fetch Bhutan retail fuel prices (Wayback backfill + live current)."""
    # Multiple FROs share a dzongkhag (e.g. Ramtokto and Jungshina are both in
    # Thimphu), so the dedup key must include city to keep all FRO rows.
    seen: set[tuple[str, str, str]] = set()
    all_rows: list[dict] = []

    for _, html in iterate_snapshots(_URL, cutoff, collapse_digits=6):
        for row in _parse(html):
            obs = row["observation_date"]
            if datetime.strptime(obs, "%Y-%m-%d").date() <= cutoff:
                continue
            key = (obs, row["fuel_product"], row["city"])
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    for row in _fetch_live():
        obs = row["observation_date"]
        if datetime.strptime(obs, "%Y-%m-%d").date() <= cutoff:
            continue
        key = (obs, row["fuel_product"], row["city"])
        if key in seen:
            continue
        seen.add(key)
        all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
