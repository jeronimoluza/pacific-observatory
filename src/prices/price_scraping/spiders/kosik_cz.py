"""Kosik.cz -- Czech Republic online grocery delivery -- https://www.kosik.cz/.

Verified live 2026-09-10 via Playwright network trace + curl_cffi
(impersonate=chrome124, though a bare browser UA also clears -- no WAF
observed). Vue SPA; the homepage HTML is a thin shell with no embedded
data, so both the category tree and the product listings come from the
internal JSON API.

Category tree: ``GET /api/front/menu/main`` returns the full nav tree in
one 294KB call -- 15 top-level departments, 1,132 leaf categories after
recursing through (inconsistently-cased) ``subCategories``/
``subcategories`` keys. This spider fetches that tree once at start and
walks every leaf.

Product listing: ``GET /api/front/page/products/flexible
?vendor=1&slug=<leaf-slug>&limit=30&search_term=`` returns
``products.items`` (name, price, unit, url, mainCategory, availability)
plus ``products.totalCount`` and a ``products.cursor`` string.

Pagination ceiling (documented, not silently dropped): the API refuses
``limit`` above 30 with ``"Using of limit over 30 products is denied ->
use cursor to load more products."`` The ``cursor`` value decodes (it's
zlib+base64) to a plain list of already-shown product ids, but round-
tripping it back as ``cursor=<value>`` (or ``after``/``afterCursor``/
``nextCursor``/``pageCursor``/etc.) returns the IDENTICAL 30 items every
time -- confirmed across many param-name guesses and with an explicit
``orderBy``. POST to the same endpoint is 405 (GET only). The site's own
frontend does not appear to use this cursor either: no "load more" /
infinite-scroll network call fires from the rendered category page, even
after clicking the visible "Zobrazit více" button and scrolling
repeatedly. So each of the 1,132 leaves yields at most its first 30
items; a live sample of 25 random leaves showed 13/25 have
totalCount > 30 (i.e. roughly half of leaf categories are truncated at
the 30-item mark; ~13 items lost on average where truncated).

Enumerability, restated for this source: rather than page-1-vs-page-2
of one query (blocked by the above), distinctness is across leaves --
verified live, two different leaf categories (c1051-klobasy "sausages"
and c1483-panske "men's [hygiene]") returned ZERO overlapping product
ids in their first-30 pages. With 1,132 such leaves this still yields a
large, non-repeating catalog (spot check: ~24 avg items/leaf across a
25-leaf random sample => catalog in the low tens of thousands), even
though depth within any single large leaf is capped.

Prices are plain decimal CZK (e.g. 109.9), not minor units -- confirmed
against several sample rows. No zero-price items observed in sampling;
`_parse_item` drops any that occur.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.kosik.cz"
_MENU_URL = f"{_BASE}/api/front/menu/main"
_FLEXIBLE_URL = f"{_BASE}/api/front/page/products/flexible"
_LIMIT = 30  # server-enforced ceiling; see module docstring


class KosikCzSpider(scrapy.Spider):
    name = "kosik_cz"
    allowed_domains = ["kosik.cz"]
    currency = "CZK"
    language = "cs"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": f"{_BASE}/",
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_MENU_URL, callback=self.parse_menu)

    def parse_menu(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("kosik_cz: menu response was not JSON")
            return

        leaves = self._leaf_slugs(data.get("categories") or [])
        logger.info(f"kosik_cz: {len(leaves)} leaf categories discovered")

        for slug in leaves:
            qs = urlencode({"vendor": 1, "slug": slug, "limit": _LIMIT, "search_term": ""})
            yield scrapy.Request(
                f"{_FLEXIBLE_URL}?{qs}",
                callback=self.parse_category,
                meta={"slug": slug},
                headers={"Referer": f"{_BASE}/{slug}"},
            )

    def _leaf_slugs(self, categories: list) -> list[str]:
        leaves: list[str] = []
        for cat in categories:
            children = cat.get("subCategories") or cat.get("subcategories") or []
            if children:
                leaves.extend(self._leaf_slugs(children))
            else:
                url = (cat.get("url") or "").lstrip("/")
                if url:
                    leaves.append(url)
        return leaves

    def parse_category(self, response):
        slug = response.meta["slug"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(f"kosik_cz: bad JSON for {slug}")
            return

        products = data.get("products") or {}
        items = products.get("items") or []
        logger.info(f"kosik_cz: {slug} total={products.get('totalCount')} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._parse_item(it, scraped_at)
            if item is not None:
                yield item

    def _parse_item(self, it: dict, scraped_at: str) -> dict | None:
        price = it.get("price")
        name = it.get("name")
        url = it.get("url")
        if not name or not url or not price:
            return None

        category = (it.get("mainCategory") or {}).get("name")
        availability = it.get("availability") or []
        available = bool(availability) and any(
            (a.get("quantity") or 0) > 0 for a in availability
        )

        return {
            "product_id": str(it.get("id")),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": available,
            "url": _BASE + url if url.startswith("/") else url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
