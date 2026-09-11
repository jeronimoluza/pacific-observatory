"""prices.sy — "أسعار سوريا" (Syria Prices), a crowd-sourced local food-price
tracker covering Syrian governorates.

MEASURED 2026-09-11: a live PHP site (`index.php?cat=<id>&gov=&search=`) with
a "report a price" feature (`report.php`) — this is user/crowd-submitted, not
a government stats office publication, but every sampled row is a real
branded grocery item with a real SYP price, a real Syrian city, and a
per-item "last updated" date. Syria currently has ZERO food-price sources of
any kind (`analytical_role: official_avg`), so this fills a total gap.

Category ids (from the site's own nav, `cat-badge` links) — only the food/
drink ones are walked here; non-food categories exist on the same platform
(2=لحومات meats?, 4=منظفات cleaning, 5=محروقات fuel, 6=مواصلات transport,
7=طبية medical, 11=خدمات services, 12=unlabeled) and are deliberately
excluded — this fetcher's scope is COICOP 01/02 only:
    1  = مواد غذائية  (general groceries — rice, sugar, oil, dairy, jam...)
    2  = لحومات        (meats/poultry, distinct from cat 3)
    3  = لحوم          (meat)
    8  = فواكه         (fruit)
    9  = مشاريب        (drinks)
    10 = خضار          (vegetables)

Each category's index page (`index.php?cat=N&gov=&search=`) already embeds
the price, currency, brand, unit and last-update date per item — no need to
hit the per-item `product.php?id=N` detail page. Sample row (cat=1, id=1):
"سكر أبيض" (white sugar), brand "الأسرة", unit "1 كغ", 15,800 ل.س (SYP),
Damascus, updated 2026/03/09.

STALENESS (measured, flag honestly): every one of the 77 food/drink items
sampled 2026-09-11 carries an update date of 2026/03 — six months old despite
the site's own "دليلك الأول لأسعار السلع والمواد اليومي" (your #1 DAILY
price guide) framing. This may be an abandoned/low-traffic crowd-price board.
Shipped anyway because every hard gate (real SYP price, real city, real
branded item, page enumerates distinct ids across categories) passes on
today's live payload — but do not assume this fetcher will find fresh rows
on every future run; a long stretch with `fetch_prices_sy` returning `None`
is expected, not a bug.

coicop_classification: classifier — free-text branded Arabic grocery names
("سمن بقري" ghee, "برغل خشن" coarse bulgur, "عدس أحمر" red lentils, "مكدوس"
eggplant preserve, ...) exactly the shape src/prices/enrich/classifier/
exists for.

UNIT: parsed from the `p-meta` weight span (e.g. "1كغ" / "1 كغ" -> "kg";
falls back to None when the unit text doesn't parse.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Syria"
_SOURCE_KEY = "prices_sy"
_BASE = "https://prices.sy/index.php"
_IDENT = ["source_key", "item_name", "subnational_area", "observation_date"]

# COICOP-01/02-relevant category ids only; see module docstring for the rest
# of the site's taxonomy (fuel/cleaning/medical/services/transport excluded).
_FOOD_CATEGORIES = {1: "مواد غذائية", 2: "لحومات", 3: "لحوم", 8: "فواكه", 9: "مشاريب", 10: "خضار"}

_CARD_RE = re.compile(
    r'<a href="product\.php\?id=(?P<id>\d+)"[^>]*>\s*<h2 class="p-title">\s*(?P<name>.*?)\s*</h2>'
    r".*?<p class=\"p-meta\">\s*<span>(?P<brand>.*?)</span>\s*<span>(?P<unit>.*?)</span>"
    r'.*?<div class="p-location">\s*\U0001F4CD\s*(?P<gov>[^|<]+?)\s*\|.*?</div>'
    r'.*?<p class="p-price">\s*(?P<price>[\d,]+)\s*<span class="p-currency">[^<]*</span>\s*</p>'
    r'\s*<span class="p-date">\s*تحديث:\s*(?P<date>[\d/]+)\s*</span>',
    re.S,
)

_UNIT_RE = re.compile(r"([\d.]+)\s*(كغ|غ|ل|مل)")
_UNIT_MAP = {"كغ": "kg", "غ": "g", "ل": "L", "مل": "mL"}


def _parse_unit(text: str) -> str | None:
    m = _UNIT_RE.search(text or "")
    if not m:
        return None
    return _UNIT_MAP.get(m.group(2))


def _parse_price(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d").date()
    except (TypeError, ValueError):
        return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lstrip("⭐").strip()


def fetch_prices_sy(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    )

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen_ids: set[str] = set()

    for cat_id, cat_label in _FOOD_CATEGORIES.items():
        try:
            resp = session.get(_BASE, params={"cat": cat_id, "gov": "", "search": ""}, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] cat=%s (%s) failed: %s", _SOURCE_KEY, cat_id, cat_label, exc)
            continue

        matches = list(_CARD_RE.finditer(resp.text))
        if not matches:
            logger.warning(
                "[%s] cat=%s (%s) -- 0 cards parsed, markup may have changed",
                _SOURCE_KEY,
                cat_id,
                cat_label,
            )
            continue

        cat_rows = 0
        for m in matches:
            item_id = m.group("id")
            if item_id in seen_ids:
                continue  # same item can recur across category pages
            seen_ids.add(item_id)

            obs_date = _parse_date(m.group("date"))
            if obs_date is None or obs_date <= cutoff:
                continue

            price = _parse_price(m.group("price"))
            if price is None or price <= 0:
                continue

            name = _clean(m.group("name"))
            brand = _clean(m.group("brand"))
            gov = _clean(m.group("gov"))
            if not name or not gov:
                continue

            item_name = f"{name} ({brand})" if brand else name
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "subnational_area": gov,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": item_name,
                "price_local": price,
                "currency": "SYP",
                "unit": _parse_unit(m.group("unit")),
                "source_url": f"https://prices.sy/product.php?id={item_id}",
                "notes": f"category={cat_label}; crowd-sourced (user 'report a price'), not an official publisher",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
            cat_rows += 1

        logger.info("[%s] cat=%s (%s) -> %d new rows", _SOURCE_KEY, cat_id, cat_label, cat_rows)

    if not rows:
        logger.info("[%s] no rows newer than cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info("[%s] %d total new rows across %d categories", _SOURCE_KEY, len(rows), len(_FOOD_CATEGORIES))
    return pd.DataFrame(rows)
