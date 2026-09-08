"""
Spider for Yemen Storez (Yemen) -- https://yemenstorez.com/.

Multi-vendor marketplace ("first Yemeni e-commerce platform" per its own
copy) linking merchants directly to customers. Server-rendered HTML with
clean OpenGraph/`product:*` meta tags on every PDP -- Tier 1A, no JS needed
to read a product once its URL is known:

  <meta property="og:title" content="...">
  <meta property="product:price:amount" content="15,000.00">
  <meta property="product:price:currency" content="YER">
  <meta property="product:availability" content="in stock" | "out of stock">
  <meta property="product:brand" content="...">
  <meta property="product:retailer_item_id" content="<slug>">

The category listing pages (`/category/<slug>`) and the `/shops` directory
are BOTH client-rendered (Vue template literals like `${randomProduct.url}`
sit unrendered in the raw HTML, and a Playwright network trace on /shops
found no product/shop-list XHR either) -- neither is usable as a discovery
surface via curl_cffi. What IS server-rendered:

  - the homepage links to 6 individual seller storefronts at
    /shop/<vendor-slug> (confirmed live 2026-09-06)
  - each /shop/<vendor-slug> page embeds real <a href="/product/...">
    anchors (5 per shop, confirmed)
  - each /product/<slug> page also links back to ~5 sibling products from
    the same shop (a "recommended" widget, not full-catalog pagination --
    no /product/ or /shop/ href set differs between a shop page and any of
    its own product pages, confirmed by diffing the link sets)

So the real crawl surface is small (6 shops x ~5 products, heavily
overlapping) but 100% real SKUs with real YER prices -- this spider walks
it as a CrawlSpider over /shop/ and /product/ paths so it also picks up any
additional shops/products the site adds without further code changes.

Currency: YER, read directly from `product:price:currency` (matches
countries.yaml default for Yemen).
"""

import logging
import re
from datetime import datetime, timezone

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_META_RE = re.compile(
    r'<meta[^>]+property="(og:[^"]+|product:[^"]+)"[^>]+content="([^"]*)"'
)


class YemenstorezYeSpider(CrawlSpider):
    name = "yemenstorez_ye"
    allowed_domains = ["yemenstorez.com"]
    start_urls = ["https://yemenstorez.com/"]
    currency = "YER"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    rules = (
        Rule(LinkExtractor(allow=(r"/shop/",)), follow=True),
        Rule(LinkExtractor(allow=(r"/product/",)), callback="parse_product", follow=True),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    def parse_product(self, response):
        metas = dict(_META_RE.findall(response.text))
        pid = metas.get("product:retailer_item_id")
        if not pid or pid in self._seen_ids:
            return
        price_raw = metas.get("product:price:amount")
        if not price_raw:
            return
        try:
            price = float(price_raw.replace(",", ""))
        except ValueError:
            return
        if price <= 0:
            return
        self._seen_ids.add(pid)
        yield {
            "product_id": pid,
            "product_name": (metas.get("og:title") or "").strip()[:500],
            "category": None,
            "price": price,
            "currency": metas.get("product:price:currency", self.currency),
            "available": metas.get("product:availability") == "in stock",
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
