"""Japan (opengov.jp) Wholesale Produce Market Prices — MAFF daily wholesale data.

Re-publication of MAFF (Ministry of Agriculture, Forestry and Fisheries)
daily wholesale trading prices across ~30 central markets for fresh
fruit/vegetable commodities. The item index page
(/en/prices/vegetable-market/) lists 71 commodity codes; each item page
(/en/prices/vegetable-market/<code>/) has a "Daily Prices (Last 30 Days)"
HTML table (`id="daily-table"`) with real ISO dates, market name, and
Mid/High/Low price in JPY/kg (the `data-unit="¥/kg"` attribute on the
adjacent chart canvas confirms the unit; the table's own "Mid Price" column
header also states "(¥/kg)"). Re-verified live 2026-08-06:
/en/prices/vegetable-market/30100/ (Daikon radish) -> 200, 391KB, daily-table
rows incl. '2026-04-02 Morioka (盛岡) ¥124', '2026-03-06 Sendai (仙台) ¥140
(High ¥189 / Low ¥76)'. Not every market reports High/Low every day (many
rows show '-' for those columns) — only Mid Price is captured as the
representative daily wholesale value; volume (tonnage) shown in the
underlying chart legend is not machine-parsed this pass.

Overlaps the same crops already covered (at a coarser national-average
grain) by the sibling opengov_retail_prices fetcher — the added value here
is per-market granularity and named cultivars the retail survey collapses
into one line. Scored as a smaller incremental add per round-1 evidence.

No auth, plain GET, one request per commodity page (71 requests). Polite
fixed delay between requests.
"""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://opengov.jp/en/prices/vegetable-market/"
_ITEM_URL = "https://opengov.jp/en/prices/vegetable-market/{code}/"
_COUNTRY = "Japan"
_CURRENCY = "JPY"
_SOURCE_KEY = "jp_opengov_wholesale_produce"
_IDENT = ["source_key", "observation_date", "item_name", "market"]
_ITEM_LINK_RE = re.compile(
    r'href="/en/prices/vegetable-market/([0-9]+)/"[^>]*>\s*([^<]+?)\s*</a>'
)
_TABLE_RE = re.compile(r'id="daily-table".*?</table>', re.S)
_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*"
    r"<td[^>]*>\xa5?([0-9,]+)</td>"
)
_REQUEST_DELAY_S = 0.3
_MAX_ITEMS = 300  # safety cap; index has 71


def _list_items(session) -> list[tuple[str, str]]:
    resp = session.get(_INDEX_URL, timeout=30)
    resp.raise_for_status()
    pairs = _ITEM_LINK_RE.findall(resp.text)
    seen: dict[str, str] = {}
    for code, name in pairs:
        seen[code] = html.unescape(name).strip()
    return sorted(seen.items())[:_MAX_ITEMS]


def _fetch_rows(session, code: str) -> tuple[str, list[tuple[str, str, str]]] | None:
    url = _ITEM_URL.format(code=code)
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] item %s fetch failed: %s", _SOURCE_KEY, code, exc)
        return None
    m = _TABLE_RE.search(resp.text)
    if not m:
        return None
    table_html = m.group(0).replace("&#165;", "\xa5").replace("¥", "\xa5")
    rows = _ROW_RE.findall(table_html)
    return url, rows


def fetch_jp_opengov_wholesale_produce(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    items = _list_items(session)
    logger.info("[%s] %d commodity items", _SOURCE_KEY, len(items))

    ts = get_scrape_ts()
    rows_out: list[dict] = []
    seen_hashes: set = set()
    for code, name in items:
        result = _fetch_rows(session, code)
        time.sleep(_REQUEST_DELAY_S)
        if result is None:
            continue
        url, rows = result
        for raw_date, market, price in rows:
            try:
                obs_date = date.fromisoformat(raw_date.strip())
            except ValueError:
                continue
            if obs_date <= cutoff:
                continue
            try:
                value = float(price.replace(",", ""))
            except ValueError:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": round(value, 2),
                "currency": _CURRENCY,
                "unit": "kg",
                "source_url": url,
                "notes": f"MAFF wholesale mid price; item_code={code}; market={market.strip()}",
                "scrape_ts": ts,
                "market": market.strip(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            if row["observation_hash"] in seen_hashes:
                continue
            seen_hashes.add(row["observation_hash"])
            del row["market"]
            rows_out.append(row)
        logger.info(
            "[%s] item=%s (%s) rows so far=%d", _SOURCE_KEY, code, name, len(rows_out)
        )

    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(rows_out), cutoff)
    return pd.DataFrame(rows_out) if rows_out else None
