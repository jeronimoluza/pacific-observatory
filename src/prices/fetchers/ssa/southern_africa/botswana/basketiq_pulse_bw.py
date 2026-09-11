"""BasketIQ Market Pulse (Botswana) — https://basketiq.co.bw/pulse/

BasketIQ is a private Botswana company that publishes "typical" retail
prices per product category, aggregated from till-verified receipts
("What are Botswana shoppers really paying? Live prices from
till-verified receipts."). Not a government publication, but a genuine
average-retail-price board -- Botswana has retailer_sku coverage
(shopsefalana_bw, spar2u_bw, choppies_ebasket_bw, farmproducts_ex_bw) but
no `official_avg` cross-retailer average, which this fills.

ACCESS (probed live 2026-09-11, plain HTTP, no WAF, no auth): the single
page https://basketiq.co.bw/pulse/ is server-rendered HTML containing
EVERY category in one page -- no pagination, no per-category endpoint.
Each row is an `<a href="/pulse/<slug>-leaf-volume" data-label="...">`
block with a `<span>` category label and a `<span>` "P <price> typical"
value, e.g.:

  <a href="/pulse/bev_soft_drinks-leaf-volume" data-label="soft drinks (per l)" ...>
    <span ...>Soft Drinks (per L)</span>
    <span ...>P 11.61 typical</span>
  </a>

MEASURED 2026-09-11: 70 category rows on the one page, spanning cereals,
dairy, oils, sugar, produce, meat, beverages, confectionery PLUS a few
non-food household/personal-care categories (Bath Soap, Laundry, Oral
Care, Deodorants, Tissue & Paper, Feminine Care) which the classifier
will route to their own COICOP leaves rather than being force-mapped
here.

ENUMERABILITY CAVEAT, recorded honestly: this source does NOT paginate
(there is no page-1-vs-page-2 check to run -- the whole board is the one
page), and re-fetching returns the SAME snapshot until BasketIQ's own
backend refreshes it. This fetcher therefore emits one `current` snapshot
per run; a same-day or same-value re-run will look like no new data only
insofar as BasketIQ hasn't moved that "typical" figure, which is expected
(this is the same shape as any live index page), not a bug.

`?` query params were tried (page=2 etc.) and returned byte-identical
content -- there is no server-side pagination to defeat here, unlike the
`prices_sy` cat=N case.

CURRENCY: BWP, read directly from the page's own "P " (Pula) price
prefix -- matches countries.yaml's Botswana default.

coicop_classification: classifier -- category labels ("Maize Meal &
Sorghum (per kg)", "Cold Meats & Deli (per kg)") are short but
descriptive enough for the ensemble classifier, and the source spans too
many COICOP classes to hand-map. coicop_codes deliberately left unset.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://basketiq.co.bw/pulse/"
_COUNTRY = "Botswana"
_SOURCE_KEY = "basketiq_pulse_bw"
_CURRENCY = "BWP"
_IDENT = ["source_key", "observation_date", "item_name"]

_ROW_RE = re.compile(
    r'<a href="(/pulse/[^"]+)"[^>]*data-label="([^"]*)"[^>]*>\s*'
    r'<span[^>]*>([^<]+)</span>\s*'
    r'<span[^>]*>\s*P\s*([\d.,]+)\s*typical\s*</span>',
    re.I | re.S,
)


def _parse(html: str) -> list[dict]:
    rows = []
    seen = set()
    for href, _data_label, label, price_str in _ROW_RE.findall(html):
        name = re.sub(r"&amp;", "&", label).strip()
        if not name or name in seen:
            continue
        try:
            price = float(price_str.replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        seen.add(name)
        rows.append(
            {
                "item_name": name,
                "price_local": price,
                "source_url": f"https://basketiq.co.bw{href}",
            }
        )
    return rows


def fetch_basketiq_pulse_bw(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    parsed = _parse(resp.text)
    if not parsed:
        logger.warning("[%s] no rows parsed from %s -- markup may have changed", _SOURCE_KEY, _URL)
        return None

    today = date.today()
    if today <= cutoff:
        logger.info("[%s] cutoff=%s is today or later, nothing to do", _SOURCE_KEY, cutoff)
        return None

    ts = get_scrape_ts()
    out_rows = []
    for r in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "current",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": r["item_name"],
            "price_local": r["price_local"],
            "currency": _CURRENCY,
            "unit": None,
            "source_url": r["source_url"],
            "notes": "BasketIQ Market Pulse -- crowd-aggregated 'typical' price from till-verified receipts, not a government series",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out_rows.append(row)

    logger.info("[%s] %d category rows for %s", _SOURCE_KEY, len(out_rows), today)
    return pd.DataFrame(out_rows)
