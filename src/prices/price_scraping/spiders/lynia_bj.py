"""
Boutique Lynia (Benin) — https://lynia-shop.com/.

WordPress + WooCommerce (WoodMart theme) storefront trading in Cotonou,
priced in XOF. Broad catalogue (1,713 products) led by beauty/health,
IT and consumer electronics, with a genuine grocery tree underneath:

    518 Supermarché                       57
    502 Petit déjeuner, Cafetière         18
    756 Café, thé et boissons sans alcool 15
    758 Épicerie sucrée                   10
    760 Bières, Vins et Spiritueux         9   <- COICOP 02.1
    757 Alimentation bébé                  5
    519 Epicerie                           3
    520 Café, thé et boissons              3
    759 Épicerie salée                     2
    373 Thé et infusions                  23

WHY scrapy_playwright AND NOT plain HTTP -- and what specifically fooled
the first two probes:

  * `curl_cffi` 403s on every path including the REST API, on chrome124,
    chrome120 and safari17_0. Title: "Vérification en cours". That alone
    would have been a `SKIP_WAF` verdict under the old (wrong) rule.
  * The block is **not** a TLS-fingerprint check and **not** a cookie gate.
    It is a User-Agent check, and the tell is brutal: a headless Chromium
    whose UA still contains the literal string "HeadlessChrome" gets the
    SAME "Vérification navigateur - Erreur rencontrée" wall as curl, even
    after a 9-second homepage warm-up. Override the context UA to a plain
    Chrome 124 string and the very first navigation -- straight to the REST
    endpoint, no warm-up, no cookies -- returns 200 JSON every time.

    Two probe runs disagreed on this site purely because one of them
    happened to set a UA and the other did not. If this source ever starts
    returning zero rows, check the UA before anything else.

  Hence PLAYWRIGHT_CONTEXTS below pins the context UA explicitly; the
  Scrapy-level USER_AGENT setting does not reach the browser.

API (WooCommerce Store API, unauthenticated):

    GET /wp-json/wc/store/v1/products?per_page=100&page=N
    -> [ {id, name, permalink, sku, categories:[{name}],
          prices:{price, currency_code, currency_minor_unit}, ...} ]
    Response headers: X-WP-Total, X-WP-TotalPages -> authoritative.

Verified live 2026-09-05: X-WP-Total = 1713, X-WP-TotalPages = 343 at
per_page=5; page 1 and page 2 return disjoint id sets, so the catalogue
genuinely paginates. Samples: "Calcium Comprimés Vegan Fortement Dosés"
15400 XOF, "Boîte À Goûter Enfant Pat Patrouille" 8500 XOF.

MINOR UNITS: WooCommerce's Store API returns integer minor units alongside
`currency_minor_unit`. Here `currency_minor_unit` is **0** for XOF, so the
integer IS the major-unit price -- but the divide is implemented properly
rather than hard-coded, because a plugin/currency change would otherwise
introduce a silent 100x error.

SCOPE: the whole catalogue, unscoped. Food is a minority (~150 of 1,713
products across the grocery tree) but non-food rows are wanted too and the
classifier assigns leaves per product.

Those category counts are an UPPER bound on COICOP 01/02, not a measurement:
the "Supermarché" tree leads with gift glassware ("Ensemble Carafe à Whisky"
66,000 XOF) before any drinkable item. Real 01/02 rows underneath include
Bordeaux 2019 at 5,500 XOF, a Saint James rum + Poliakov vodka set at 36,950
XOF, Nespresso Vertuo capsules at 47,700 XOF and Lindt moulages at 5,600 XOF.
A capped test run samples newest-first and will look non-food (school
supplies, books, vitamins) — that is the site's ordering, not a broken spider.

Page family parsed: **API** (the spider navigates only to REST URLs). The
emitted row URL is the WooCommerce `permalink`, a real browsable PDP that
this spider does not itself fetch.
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://lynia-shop.com"
API = f"{BASE_URL}/wp-json/wc/store/v1/products"
PAGE_SIZE = 100
MAX_PAGES = 60

_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _extract_json(response):
    """Pull the JSON body out of a scrapy-playwright navigation response.

    Chromium wraps `content-type: application/json` navigations in
    `<html><body><pre>{...}</pre></body></html>`, so `response.json()`
    fails. Same trap as express_market_cm.
    """
    pre = response.css("pre::text").get()
    raw = pre if pre is not None else response.text
    return json.loads(raw)


class LyniaBjSpider(scrapy.Spider):
    name = "lynia_bj"
    allowed_domains = ["lynia-shop.com"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        # The browser UA is the whole ballgame on this site -- see docstring.
        "PLAYWRIGHT_CONTEXTS": {
            "default": {
                "user_agent": _CHROME_UA,
                "locale": "fr-FR",
            }
        },
    }

    def _page_request(self, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{API}?per_page={PAGE_SIZE}&page={page}",
            callback=self.parse_page,
            errback=self.errback,
            meta={
                "page": page,
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            },
            dont_filter=True,
        )

    async def start(self):
        yield self._page_request(1)

    def errback(self, failure):
        logger.warning(f"{self.name}: request failed -- {failure.value!r}")

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            products = _extract_json(response)
        except (ValueError, json.JSONDecodeError):
            logger.warning(
                f"{self.name}: non-JSON at page {page} "
                f"(UA check? first 200 chars: {response.text[:200]!r})"
            )
            return
        if not isinstance(products, list) or not products:
            return

        total_pages = response.headers.get("X-WP-TotalPages")
        total_pages = int(total_pages) if total_pages else None
        total = response.headers.get("X-WP-Total")

        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for p in products:
            prices = p.get("prices") or {}
            raw = prices.get("price")
            if raw in (None, ""):
                continue
            minor = prices.get("currency_minor_unit")
            try:
                value = float(raw) / (10 ** int(minor if minor is not None else 0))
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue

            name = html.unescape(p.get("name") or "").strip()
            if not name:
                continue

            cats = p.get("categories") or []
            category = html.unescape(
                " > ".join(c.get("name", "") for c in cats[:2])
            ).strip(" >")

            yielded += 1
            yield {
                "product_id": str(p.get("sku") or p.get("id")),
                "product_name": name[:500],
                "category": category,
                "price": f"{value:g}",
                "currency": prices.get("currency_code") or self.currency,
                "available": bool(p.get("is_in_stock", True)),
                "url": p.get("permalink") or f"{BASE_URL}/?p={p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"{self.name}: page={page} items={len(products)} yielded={yielded} "
            f"x-wp-total={total} x-wp-totalpages={total_pages}"
        )

        if len(products) >= PAGE_SIZE and page < MAX_PAGES:
            if total_pages is None or page < total_pages:
                yield self._page_request(page + 1)
