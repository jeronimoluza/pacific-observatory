"""
Al Jazira Supermarkets (Bahrain) — https://www.aljazirasupermarkets.com/.

Grocery chain (15 stores + express gas-station outlets, operating since
1965) on the WaveGrocery SaaS platform (Next.js pages router; footer credits
"Made with love by Wave Grocery"). The rendered category pages themselves
only carry i18n dictionary strings client-side, but Next.js's own data
route exposes the server-fetched props directly as JSON:

    GET /_next/data/<buildId>/categories/<slug>/<subslug>.json
    Header: x-nextjs-data: 1
    -> {"pageProps": {..., "categoriesFromFile": [...], "initialProducts": [...]}}

`buildId` is scraped from the homepage HTML (`"buildId":"..."` in the
embedded Next.js data blob) at spider start. `categoriesFromFile` is the
full category tree (23 top departments); its leaf nodes' `fullSlug` values
(384 leaves: produce/fresh-fruits, fresh-meat-fish/beef, bakery/cakes,
dairy, beverages, ...) are each walked once. `initialProducts` on a leaf
page is the first tranche (~30 items) server-rendered for that category —
no further pagination cursor was found in the payload, so this spider
takes that tranche per leaf; walking all 384 leaves still covers the full
department breadth of a real grocery catalog.

Prices (`finalPrice`) are integers in fils, BHD's minor unit
(`unitOfMeasurementBaseCoefficient: 1000` confirms the scale) — divided by
1000 to get the BHD decimal amount. Rows with `available: false`,
`enabled: false` or `isExcludedFromCatalog: true` are dropped.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.aljazirasupermarkets.com"
_BUILD_ID_RE = re.compile(r'"buildId":"([^"]+)"')

_DATA_HEADERS = {
    "x-nextjs-data": "1",
    "purpose": "prefetch",
}


class AljaziraBhSpider(scrapy.Spider):
    name = "aljazira_bh"
    allowed_domains = ["aljazirasupermarkets.com"]
    currency = "BHD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_home, errback=self.errback
        )

    def parse_home(self, response):
        match = _BUILD_ID_RE.search(response.text)
        if not match:
            logger.error(f"{self.name}: buildId not found on homepage")
            return
        build_id = match.group(1)
        logger.info(f"{self.name}: buildId={build_id}")
        # Any leaf category page carries the full tree in categoriesFromFile;
        # use bakery/cakes (known to exist) to bootstrap the tree.
        yield self._data_request(
            build_id,
            "categories/bakery/cakes",
            callback=self.parse_tree,
            meta={"build_id": build_id},
        )

    def parse_tree(self, response):
        build_id = response.meta["build_id"]
        try:
            data = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON tree response from {response.url}")
            return

        categories = data.get("pageProps", {}).get("categoriesFromFile") or []
        leaves = []

        def walk(nodes):
            for node in nodes:
                subs = node.get("subCategories") or []
                if subs:
                    walk(subs)
                else:
                    full_slug = node.get("fullSlug")
                    if full_slug:
                        leaves.append(full_slug)

        walk(categories)
        logger.info(f"{self.name}: leaf categories found={len(leaves)}")

        # bakery/cakes' own products are in this same response — parse them too.
        yield from self._extract_products(data, "categories/bakery/cakes")

        for slug in leaves:
            if slug == "categories/bakery/cakes":
                continue
            yield self._data_request(
                build_id, slug, callback=self.parse_category, meta={"slug": slug}
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return
        yield from self._extract_products(data, slug)

    def _extract_products(self, data, slug):
        products = data.get("pageProps", {}).get("initialProducts") or []
        found = 0
        for product in products:
            if (
                not product.get("available")
                or not product.get("enabled")
                or product.get("isExcludedFromCatalog")
            ):
                continue
            final_price = product.get("finalPrice")
            if not final_price:
                continue
            name = (product.get("name") or "").strip()
            path = product.get("slug") or ""
            if not name or not path:
                continue

            found += 1
            yield {
                "product_id": product.get("sku") or product.get("_id") or "",
                "product_name": name[:500],
                "category": slug,
                "price": f"{final_price / 1000:.3f}",
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}{path}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            f"{self.name}: category={slug} products={len(products)} yielded={found}"
        )

    def _data_request(self, build_id, slug, callback, meta):
        return scrapy.Request(
            f"{BASE_URL}/_next/data/{build_id}/{slug}.json",
            callback=callback,
            errback=self.errback,
            headers=_DATA_HEADERS,
            meta=meta,
        )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
