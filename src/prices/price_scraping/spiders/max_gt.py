"""
Spider for Max Guatemala -- https://www.max.com.gt/.

Grupo Distelsa general-merchandise retailer (electronics, appliances,
furniture, toys -- not narrowly home-improvement despite one
"mejora-del-hogar" department among 22). Next.js storefront; category
listing pages embed a `productsList` array in __NEXT_DATA__
(props.pageProps.productsList) but it carries no price -- pricing lives
only on the individual product detail page's
props.pageProps.product.cachedPrices. Two-hop spider: walk leaf categories
for slugs, then fetch each /producto/<slug> page for the real GTQ price.

In-category pagination could not be confirmed: ?page=2 and ?p=2 on a
listing page both return the identical first page (client-side listing
uses Constructor.io, cnstrc.com, not a URL-drivable SSR param).
Enumerability is instead proven across the site's 590 real leaf categories
(server-sitemap.xml, 3+ path segments, e.g.
linea-blanca/refrigeracion/vineras) -- two distinct leaf categories
returned disjoint productsList SKU sets (0 overlap), confirming this is a
genuine category tree walk, not a single curated carousel.

Category discovery samples the leaf-category slice of server-sitemap.xml
at a fixed stride to stay bounded.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.max.com.gt"
_SITEMAP_URL = "https://www.max.com.gt/server-sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_CATEGORY_STRIDE = 12  # sample every Nth leaf category (~49 of 590)


class MaxGtSpider(scrapy.Spider):
    name = "max_gt"
    allowed_domains = ["max.com.gt"]
    currency = "GTQ"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        leaves = [loc for loc in locs if loc.count("/") >= 5]
        sampled = leaves[::_CATEGORY_STRIDE]
        logger.info(
            f"{self.name}: sampled {len(sampled)}/{len(leaves)} leaf categories"
        )
        for url in sampled:
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: bad __NEXT_DATA__ JSON at {response.url}")
            return
        pp = data.get("props", {}).get("pageProps", {})
        category = pp.get("categoryTitle")
        for p in pp.get("productsList") or []:
            slug = p.get("slug")
            if slug:
                yield scrapy.Request(
                    f"{_BASE}/producto/{slug}",
                    callback=self.parse_product,
                    meta={"category": category},
                )

    def parse_product(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: bad __NEXT_DATA__ JSON at {response.url}")
            return
        product = data.get("props", {}).get("pageProps", {}).get("product") or {}
        item = self._item(product, response.meta.get("category"), response.url)
        if item:
            yield item

    def _item(self, product: dict, category: str | None, url: str):
        name = (product.get("title") or "").strip()
        sku = product.get("sku")
        if not name or not sku:
            return None
        cached_prices = product.get("cachedPrices") or {}
        sales_price = (cached_prices.get("salesPrice") or {}).get("value")
        regular_price = (cached_prices.get("regularPrice") or {}).get("value")
        price = sales_price if sales_price is not None else regular_price
        if price is None:
            return None
        return {
            "product_id": str(sku),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
