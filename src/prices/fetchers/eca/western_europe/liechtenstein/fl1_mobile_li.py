"""FL1 (Telecom Liechtenstein AG) -- domestic mobile subscription plan
catalogue, snapshot.

FL1 is the rebranded consumer storefront of Telecom Liechtenstein AG (the
country's incumbent domestic telecom operator; telecom.li now serves as the
wholesale-only portal and canonicalises visitors to fl1.li for consumer
plans -- verified live 2026-09-01, telecom.li's own <title> reads
"Wholesale - FL1"). This is therefore a single company, not two sources.

fl1.li is a WordPress site whose plan pages embed each mobile subscription
as a "Konfigurator" checkbox card, server-rendered plain HTML (curl_cffi
impersonate=chrome124 returns full content, no Playwright needed). Four
plan-family pages, each listing 5 tiers (XS/S/M/L/XL):

  /mobile/free-abos/        FL1 FREE!  (standard)
  /mobile/free-young-abos/  FL1 FREE! Young (under-26 discount)
  /mobile/life-abos/        FL1 LIFE!  (standard)
  /mobile/life-young-abos/  FL1 LIFE! Young (under-26 discount)

Each plan card carries a stable WooCommerce-style product id
(`input.flcongradioprdcatlist[value]`), a name (`div.product-heading`), and
a monthly CHF price (`.product-price .regulapriced`). Verified live
2026-09-01: 20 distinct plans, e.g. "FL1 LIFE! XS" (id 32531) CHF 19.90/mo,
"FL1 FREE! XL" (id 36427) CHF 99.90/mo -- re-fetched cold and matched.

coicop_classification: source_curated -- the whole catalogue is mobile
telephone service plans, COICOP 08.3.0 (matches the majority convention in
this repo for mobile-tariff sources, e.g. Sierra Leone's africell_tariffs,
Burkina Faso's orange_mobile_tariff; NOT the 08.2 used by the one Norway
outlier).

period_kind: snapshot, gated on `today <= cutoff` (this is a live current
price-list page with no dated "effective from" -- price changes are picked
up as a new observation_date row with a different price on a later run,
same pattern as `fm_fsmtc_tariff`).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Liechtenstein"
_SOURCE_KEY = "fl1_mobile_li"
_BASE = "https://www.fl1.li/mobile/"
_PLAN_PAGES = [
    "free-abos",
    "free-young-abos",
    "life-abos",
    "life-young-abos",
]
_COICOP_CODE = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]
_FALLBACK_DATE = date(2015, 1, 1)


def _parse_plans(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for card in soup.select("div.products-category"):
        heading = card.find("div", class_="product-heading")
        price_el = card.select_one(".regulapriced")
        input_el = card.find("input", class_="flcongradioprdcatlist")
        if heading is None or price_el is None:
            continue
        name = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        price_txt = price_el.get_text(strip=True).replace("'", "")
        try:
            price = float(price_txt)
        except ValueError:
            continue
        if not name or price <= 0:
            continue
        plan_id = input_el.get("value") if input_el else None
        out.append(
            {
                "product_id": plan_id,
                "item_name": name,
                "price_local": price,
                "source_url": url,
            }
        )
    return out


def fetch_fl1_mobile_li(cutoff: date) -> pd.DataFrame | None:
    today = datetime.now(timezone.utc).date()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    parsed: list[dict] = []
    for slug in _PLAN_PAGES:
        url = _BASE + slug + "/"
        try:
            resp = session.get(
                url,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        plans = _parse_plans(resp.text, url)
        if not plans:
            logger.warning("[%s] no plans parsed from %s", _SOURCE_KEY, url)
        parsed.extend(plans)

    # De-dup by product_id across pages (defensive -- pages are disjoint
    # plan families in practice, but a stable id is the right dedup key).
    seen = set()
    deduped = []
    for p in parsed:
        key = p["product_id"] or p["item_name"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    if not deduped:
        logger.warning("[%s] no rows parsed from any plan page", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in deduped:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": "CHF",
            "unit": "plan",
            "source_url": p["source_url"],
            "notes": f"FL1 mobile plan catalogue, product_id={p['product_id']}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
