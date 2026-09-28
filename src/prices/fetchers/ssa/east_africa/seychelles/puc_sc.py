"""PUC (Public Utilities Corporation, Seychelles) -- electricity and water/
sewerage tariff schedules.

Tariff figures are not in the static page HTML -- they load via an
"xyz-snippet" WordPress AJAX widget: each tariff table sits behind
`POST /wp-admin/admin-ajax.php` with `action=run_xyz_shortcode` and a
`snippet=<name>` key, guarded by a `nonce` that is embedded in the parent
page's own HTML (`xyzAjax = {"url": ..., "nonce": "..."}`) and must be
re-read per run rather than hardcoded. Verified live 2026-09-28: the
returned fragment is a plain wpDataTable <table>; `post_id` is optional
(worked with and without it).

Two tariff pages, same mechanism:
- /electricity-tariffs/ -- snippets "Electricity-Domestic-110/120/130"
  (the three residential single/three-phase bands; commercial/government/
  bulk tariffs on the same page are out of scope, same narrow-residential
  convention as ceb_electricity_tariff.py, cie_tariff.py).
- /water-tariffs/ -- snippet "Water-Domestic-Sector", a single table with
  two charge columns per consumption band: "WATER CHARGES (SR)" and
  "SEWERAGE CHARGES (SR)".

Neither page states an explicit "effective from" date, so this fetcher
snapshots with period_kind="effective_from" and effective_from = the
scrape date -- the honest close per the skill's tariff-schedule guidance
when only a current schedule (no dated revision) is published.

COICOP: electricity -> 04.5.1. Water charges -> 04.4.1 (water supply).
Sewerage charges -> 04.4.3 (sewerage collection). Wide across two 3-digit
classes (04.4 and 04.5), so `coicop_codes` lists all three.

Currency: SCR.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_AJAX_URL = "https://www.puc.sc/wp-admin/admin-ajax.php"
_ELEC_PAGE_URL = "https://www.puc.sc/electricity-tariffs/"
_WATER_PAGE_URL = "https://www.puc.sc/water-tariffs/"
_COUNTRY = "Seychelles"
_CURRENCY = "SCR"
_SOURCE_KEY = "puc_sc"
_IDENT = ["source_key", "observation_date", "item_name"]

_NONCE_RE = re.compile(r'xyzAjax\s*=\s*\{"url":"[^"]+","nonce":"([^"]+)"\}')

_ELEC_SNIPPETS = {
    "Electricity-Domestic-110": "Domestic tariff 110 (demand <=2.4 kVA)",
    "Electricity-Domestic-120": "Domestic tariff 120 (2.4-9.6 kVA)",
    "Electricity-Domestic-130": "Domestic tariff 130 (demand >=9.6 kVA)",
}
_NUMBER_RE = re.compile(r"[\d,]+\.\d+|\d+")


def _get_nonce(session, page_url: str) -> str | None:
    resp = session.get(page_url, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, page_url)
        return None
    m = _NONCE_RE.search(resp.text)
    return m.group(1) if m else None


def _fetch_snippet(session, snippet: str, referer: str, nonce: str) -> str | None:
    resp = session.post(
        _AJAX_URL,
        data={"action": "run_xyz_shortcode", "snippet": snippet, "nonce": nonce},
        headers={"Referer": referer},
        timeout=30,
    )
    if resp.status_code != 200 or not resp.text.strip():
        logger.warning(
            "[%s] snippet %s failed HTTP %s", _SOURCE_KEY, snippet, resp.status_code
        )
        return None
    return resp.text


def _label_value_pairs(table_html: str) -> list[tuple[str, float]]:
    """Rows with exactly 2 <td> cells: (label text, last numeric token)."""
    soup = BeautifulSoup(table_html, "html.parser")
    out: list[tuple[str, float]] = []
    for tr in soup.find_all("tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        tds = [t for t in tds if t]
        if len(tds) != 2:
            continue
        label, value_text = tds
        nums = _NUMBER_RE.findall(value_text)
        if not nums:
            continue
        try:
            value = float(nums[-1].replace(",", ""))
        except ValueError:
            continue
        out.append((label, value))
    return out


def _electricity_rows(session, effective_date: date, scrape_ts: str) -> list[dict]:
    nonce = _get_nonce(session, _ELEC_PAGE_URL)
    if nonce is None:
        logger.warning("[%s] could not read nonce from %s", _SOURCE_KEY, _ELEC_PAGE_URL)
        return []
    rows: list[dict] = []
    for snippet, label in _ELEC_SNIPPETS.items():
        html = _fetch_snippet(session, snippet, _ELEC_PAGE_URL, nonce)
        if html is None:
            continue
        for row_label, value in _label_value_pairs(html):
            item_name = f"Electricity, {label} -- {row_label}"
            unit = "kWh" if "kwh" in row_label.lower() else "kVA"
            row = {
                "observation_date": effective_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": None,
                "source_key": _SOURCE_KEY,
                "coicop_code": "04.5.1",
                "item_name": item_name,
                "price_local": value,
                "currency": _CURRENCY,
                "unit": unit,
                "source_url": _ELEC_PAGE_URL,
                "notes": f"snippet={snippet}",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def _water_rows(session, effective_date: date, scrape_ts: str) -> list[dict]:
    nonce = _get_nonce(session, _WATER_PAGE_URL)
    if nonce is None:
        logger.warning("[%s] could not read nonce from %s", _SOURCE_KEY, _WATER_PAGE_URL)
        return []
    html = _fetch_snippet(session, "Water-Domestic-Sector", _WATER_PAGE_URL, nonce)
    if html is None:
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for tr in soup.find_all("tr")[1:]:  # skip header row
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        tds = [t for t in tds if t]
        if len(tds) != 3:
            continue
        band, water_charge, sewerage_charge = tds
        for charge_text, coicop_code, label in (
            (water_charge, "04.4.1", "water charge"),
            (sewerage_charge, "04.4.3", "sewerage charge"),
        ):
            nums = _NUMBER_RE.findall(charge_text)
            if not nums:
                continue
            try:
                value = float(nums[-1].replace(",", ""))
            except ValueError:
                continue
            row = {
                "observation_date": effective_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": None,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop_code,
                "item_name": f"Domestic {label}, {band} m3/month",
                "price_local": value,
                "currency": _CURRENCY,
                "unit": "m3",
                "source_url": _WATER_PAGE_URL,
                "notes": "snippet=Water-Domestic-Sector",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_puc_sc(cutoff: date) -> pd.DataFrame | None:
    effective_date = date.today()
    if effective_date <= cutoff:
        logger.info(
            "[%s] effective_date=%s <= cutoff=%s, skipping",
            _SOURCE_KEY,
            effective_date,
            cutoff,
        )
        return None

    session = get_session()
    scrape_ts = get_scrape_ts()
    rows = _electricity_rows(session, effective_date, scrape_ts)
    rows += _water_rows(session, effective_date, scrape_ts)

    if not rows:
        logger.warning("[%s] No tariff rows parsed", _SOURCE_KEY)
        return None

    logger.info(
        "[%s] %d tariff rows (effective %s)", _SOURCE_KEY, len(rows), effective_date
    )
    return pd.DataFrame(rows)
