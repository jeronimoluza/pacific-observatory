"""NAMBoard / EHIS weekly market price board — Eswatini fresh-produce prices.

Eswatini's National Agricultural Marketing Board (NAMBoard, namboard.co.sz)
links its "Weekly Buying Prices" menu item to a separate portal,
``www.ehis.co.sz`` (Eswatini Horticulture Information System), which
publishes a fixed nomenclature of ~67 fresh fruit/vegetable commodities as a
server-rendered HTML table, refreshed weekly. Verified live 2026-09-11.

Four pages share the identical table markup and commodity list, differing
only in price and which physical market/board the price applies to:

    /Portal/Info/buyingprice   NAMBoard's own national buying (producer) price
    /Portal/Info/Siteki        Siteki fresh-produce market board
    /Portal/Info/Nhlangano     Nhlangano fresh-produce market board
    /Portal/Info/PiggsPeak     Piggs Peak fresh-produce market board

All four returned exactly 67 rows with genuinely different prices per item
(e.g. Lettuce: buyingprice unpriced-in-this-list, Siteki E4.50, Nhlangano
E6.00, Piggs Peak E4.50) — this is a fixed published commodity nomenclature,
not a broken-fetch flat-count artifact; confirmed by the differing values
across pages fetched in the same run.

Table shape: <table id="example"> with columns Product | Unit | Price |
Date (a "<start> TO <end>" validity range for the current week). The three
named-market pages additionally emit a hidden ``display:none`` sort <td>
before Product, holding the raw price used for client-side default sort —
dropped here. The national buyingprice page has no hidden column.

Price text is prefixed with a currency-symbol-as-letter on the market pages
("E4.50" = SZL 4.50, "E" for Emalangeni) but not on the buyingprice page
("9.50" plain) — both strip to the same numeric parse. Currency is fixed to
SZL (matches countries.yaml).

No date parameter or history endpoint was found: the site always shows the
CURRENT week only (no historical archive), so this fetcher takes a single
snapshot per run rather than walking a day range. `period_kind` is
`weekly_avg` and `observation_date` is the period END date parsed out of the
"<start> TO <end>" text.

coicop_classification: classifier — same reasoning as ocpv_infoprix_civ and
the two existing Eswatini official_avg sources (wfp_swz, fews_swz): a
free-text produce list (grade suffixes like "Grade A"/"Grade B" included) is
exactly what the downstream classifier exists for.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Eswatini"
_SOURCE_KEY = "namboard_ehis_swz"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "subnational_area"]

_PAGES: dict[str, str] = {
    "National": "https://www.ehis.co.sz/Portal/Info/buyingprice",
    "Siteki": "https://www.ehis.co.sz/Portal/Info/Siteki",
    "Nhlangano": "https://www.ehis.co.sz/Portal/Info/Nhlangano",
    "Piggs Peak": "https://www.ehis.co.sz/Portal/Info/PiggsPeak",
}

_UNIT_MAP = {
    "p/kg": "kg",
    "each": "each",
    "bundle": "bundle",
    "cob": "cob",
}


def _norm_unit(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    key = raw.lower()
    if key in _UNIT_MAP:
        return _UNIT_MAP[key]
    # e.g. "10 KG" -> "10kg"
    m = re.match(r"^(\d+)\s*kg$", key)
    if m:
        return f"{m.group(1)}kg"
    return key


def _num(text: str) -> float | None:
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return val if val > 0 else None


def _parse_page(html: str) -> list[tuple[str, str, str, str]]:
    """Return list of (product, unit, price_text, date_text) from the table."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="example") or soup.find("table")
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        return []
    out = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        if tds[0].get("style", "").replace(" ", "") == "display:none;":
            tds = tds[1:]
        if len(tds) < 4:
            continue
        vals = [td.get_text(" ", strip=True) for td in tds[:4]]
        out.append(tuple(vals))
    return out


def fetch_namboard_ehis_swz(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    ts = get_scrape_ts()
    rows: list[dict] = []

    for market, url in _PAGES.items():
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] %s failed: %s", _SOURCE_KEY, market, exc)
            continue

        parsed = _parse_page(resp.text)
        if not parsed:
            logger.warning("[%s] %s: no table rows found", _SOURCE_KEY, market)
            continue

        for product, unit_raw, price_text, date_text in parsed:
            product = product.strip()
            if not product:
                continue
            price = _num(price_text)
            if price is None:
                continue
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", date_text)
            if not dates:
                continue
            obs_date = dates[-1]  # period END date
            if date.fromisoformat(obs_date) <= cutoff:
                continue
            unit = _norm_unit(unit_raw)
            row = {
                "observation_date": obs_date,
                "period_kind": "weekly_avg",
                "country": _COUNTRY,
                "subnational_area": market,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": product,
                "price_local": round(price, 2),
                "currency": "SZL",
                "unit": unit,
                "source_url": url,
                "notes": (
                    f"NAMBoard/EHIS weekly {'national buying' if market == 'National' else 'market'} "
                    f"price board; period {date_text}"
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info("[%s] nothing newer than cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info("[%s] %d rows across %d market page(s)", _SOURCE_KEY, len(rows), len(_PAGES))
    return pd.DataFrame(rows)
