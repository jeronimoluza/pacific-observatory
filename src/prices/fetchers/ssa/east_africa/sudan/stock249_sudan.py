"""stock249.com — Sudanese commodity/consumer price board ("Elrayah Group"
site, primarily an FX black-market-rate tracker with two structured
commodity-price pages that this fetcher reads):

    /agri-sudan       raw agricultural crops -- sorghum varieties, millet,
                       sesame, sunflower seed, roasted mixed nuts/seeds,
                       groundnuts, dried okra powder (food) PLUS cotton and
                       three grades of gum arabic (industrial, excluded)
    /consumer-sudan   packaged staples -- sugar, flour, cooking oil, rice,
                       lentils, tea (food) PLUS cement, rebar, bricks, sand,
                       gravel (construction materials, excluded)

MEASURED 2026-09-11: both pages embed a JSON-LD `@graph` with an `ItemList`
of `Product`+`Offer` nodes, each carrying `priceCurrency: "SDG"` and a
numeric `price`. The page also carries an FAQPage node explicitly citing its
source: "الأسعار منقولة من نشرات رسمية: سوق القضارف ... والإدارة العامة
لتسويق المحاصيل بإقليم النيل الأزرق" (prices are drawn from official
bulletins: Al-Gadarif market and the Blue Nile region's crop-marketing
directorate) -- an official-bulletin republisher, not a retailer. Both
pages carry `<lastmod>` of the current date in `/sitemap.xml` (daily
cadence), unlike the flatter/staler `prices.sy` (Syria) crowd-board found
in the same campaign pass.

Sudan had ZERO food-price sources of any analytical_role before this.

_FOOD_ITEMS is an EXCLUDE-list approach (not an allow-list): both source
pages are already food-and-commodity themed, so only the handful of
genuinely non-food items (cotton, gum arabic, cement/rebar/bricks/sand/
gravel) are filtered out by substring match. This is more maintainable
than hand-listing every food name the board might add.

coicop_classification: classifier -- free-text Sudanese commodity/crop
names (many with local varietal terms: "فتريتة", "ود باكو", "ويكة") are
exactly the classifier's shape. coicop_codes left unset.

UNIT: the item name itself encodes the unit ("جوال" sack/bag, "قنطار"
quintal/100kg, "كيلة" a local volume measure, "كيلو" kg) -- left in
`item_name` verbatim rather than parsed out, because the measures are
non-standard local units (a "جوال" bag size varies by commodity) and
inventing a numeric kg-equivalent would be a guess. `unit` column is null.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Sudan"
_SOURCE_KEY = "stock249_sudan"
_BASE = "https://stock249.com"
_PAGES = ["/agri-sudan", "/consumer-sudan"]
_IDENT = ["source_key", "item_name", "observation_date"]

# Non-food items to drop from the two otherwise food-themed pages.
_EXCLUDE_SUBSTRINGS = (
    "القطن",  # cotton
    "صمغ",  # gum arabic (industrial/export commodity, not a food ingredient here)
    "الأسمنت",  # cement
    "حديد تسليح",  # rebar
    "طوبة",  # bricks
    "الرمل",  # sand
    "الزلط",  # gravel
)


def _extract_items(html: str) -> list[dict]:
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    for raw in blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        candidates = graph if graph else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "ItemList":
                out = []
                for el in node.get("itemListElement", []):
                    item = el.get("item", {})
                    offer = item.get("offers", {})
                    out.append(
                        {
                            "name": item.get("name"),
                            "price": offer.get("price"),
                            "currency": offer.get("priceCurrency"),
                        }
                    )
                return out
    return []


def fetch_stock249_sudan(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] today (%s) not after cutoff=%s", _SOURCE_KEY, today, cutoff)
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen_names: set[str] = set()

    for path in _PAGES:
        try:
            resp = session.get(_BASE + path, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] %s failed: %s", _SOURCE_KEY, path, exc)
            continue

        items = _extract_items(resp.text)
        if not items:
            logger.warning("[%s] %s -- 0 items parsed, markup may have changed", _SOURCE_KEY, path)
            continue

        page_rows = 0
        for it in items:
            name = (it.get("name") or "").strip()
            price = it.get("price")
            currency = it.get("currency")
            if not name or price is None or currency != "SDG":
                continue
            if any(bad in name for bad in _EXCLUDE_SUBSTRINGS):
                continue
            if name in seen_names:
                continue
            seen_names.add(name)
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            row = {
                "observation_date": today.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": name,
                "price_local": price,
                "currency": "SDG",
                "unit": None,
                "source_url": f"{_BASE}{path}",
                "notes": "official-bulletin republisher (Al-Gadarif market / Blue Nile crop-marketing directorate); unit is embedded in item_name (jawal=sack, gantar=quintal, keila=local measure)",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
            page_rows += 1

        logger.info("[%s] %s -> %d food rows", _SOURCE_KEY, path, page_rows)

    if not rows:
        logger.info("[%s] no rows for %s", _SOURCE_KEY, today)
        return None

    logger.info("[%s] %d total rows across %d pages", _SOURCE_KEY, len(rows), len(_PAGES))
    return pd.DataFrame(rows)
