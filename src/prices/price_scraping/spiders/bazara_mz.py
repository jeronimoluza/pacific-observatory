"""
Bazara (Mozambique) — https://bazara.co.mz/.

Magento 2 marketplace ("compras online com confiança", Maputo, M-Pesa
checkout). The storefront's own /graphql endpoint is open with no auth.
Verified live: products(filter:{category_id:{eq:"2"}}) (the Default/root
category id) returns the full ~9,000-product catalog directly with no
categoryList fan-out needed.

URL TRAP: url_key + the store's global url_suffix (".html", also what the
GraphQL `url_suffix` field reports) does NOT reliably resolve — some
products 404 with the suffix, some 404 without it, inconsistently (mixed
bulk-import history, not predictable from SKU prefix or url_suffix field).
Introspection is disabled and there is no sitemap.xml (robots.txt disallows
/, and Magento's usual /sitemap.xml 404s). The one URL that resolved for
every sampled product regardless of rewrite state is Magento's canonical,
rewrite-independent route: /catalog/product/view/id/<entity id>/ — this
spider requests `id` from GraphQL and builds URLs from that instead of
url_key.

Catalog is a general marketplace (electronics, tools, clothing) but with a
real grocery slice: "Alimentos" (622) + "Bebidas" (225) top-level
categories confirmed via categoryList, MZN throughout. COICOP left to the
classifier given the wide catalog.
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://bazara.co.mz/graphql"
BASE_URL = "https://bazara.co.mz"
PAGE_SIZE = 100
MAX_PAGES = 200

_QUERY = """
{ products(filter: {category_id: {eq: "2"}}, pageSize: %d, currentPage: %d) {
    total_count
    items {
      id
      sku
      name
      price_range { minimum_price { final_price { value currency } } }
    }
  }
}
"""


class BazaraMzSpider(scrapy.Spider):
    name = "bazara_mz"
    allowed_domains = ["bazara.co.mz"]
    currency = "MZN"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 4,
    }

    def start_requests(self):
        yield self._page_request(1)

    def _page_request(self, page):
        return scrapy.Request(
            GRAPHQL_URL,
            method="POST",
            body=json.dumps({"query": _QUERY % (PAGE_SIZE, page)}),
            headers={"Content-Type": "application/json"},
            callback=self.parse_page,
            meta={"page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON response page={page}")
            return

        block = (data.get("data") or {}).get("products") or {}
        items = block.get("items") or []
        logger.info(
            f"{self.name}: page={page} count={len(items)} total={block.get('total_count')}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in items:
            name = (p.get("name") or "").strip()
            price_block = ((p.get("price_range") or {}).get("minimum_price") or {}).get(
                "final_price"
            ) or {}
            value = price_block.get("value")
            pid = p.get("id")
            if not name or value is None or pid is None:
                continue
            yield {
                "product_id": str(p.get("sku") or pid),
                "product_name": html.unescape(name)[:500],
                "category": None,
                "price": str(value),
                "currency": price_block.get("currency") or self.currency,
                "available": True,
                "url": f"{BASE_URL}/catalog/product/view/id/{pid}/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if items and page < MAX_PAGES:
            yield self._page_request(page + 1)
