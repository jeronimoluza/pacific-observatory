"""
Spider for Marketplace.vu -- https://marketplace.vu/.

The Flutter web app at https://app.marketplace.vu embeds a public Supabase
publishable key and reads product/shop data through PostgREST. We query the
same public API, limited to visible, approved, nonzero-price rows from enabled
non-test shops. This source is scoped to non-food specialized/household goods
where possible; food and liquor-heavy categories are skipped.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://kntlasipuldprxqdtfqk.supabase.co/rest/v1/products"
_APIKEY = "sb_publishable_GI1BfRhJE40IgS6LGH1Vzw_2ERrg1CP"
_SELECT = ",".join(
    [
        "id",
        "business_id",
        "name",
        "sku",
        "price",
        "stock_available",
        "visible_on_web",
        "moderation_status",
        "category:categories!products_category_id_fkey(name,name_language2)",
        "subcategory:categories!products_subcategory_id_fkey(name,name_language2)",
        "business:businesses!inner(name,address,enabled,is_test,currency_symbol,hide_out_of_stock_products,hide_zero_price_products,url_slug)",
    ]
)
_PAGE_SIZE = 500
_MAX_PAGES = 20
_SKIP_CATEGORY_TOKENS = (
    "grocer",
    "epicerie",
    "liquid",
    "liquide",
    "wine",
    "vins",
    "beer",
    "spirit",
    "food",
    "aliment",
)


class MarketplaceVuSpider(scrapy.Spider):
    name = "marketplace_vu"
    allowed_domains = ["kntlasipuldprxqdtfqk.supabase.co", "marketplace.vu"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield self._request(0)

    def _request(self, offset: int) -> scrapy.Request:
        query = urlencode(
            {
                "select": _SELECT,
                "visible_on_web": "eq.true",
                "moderation_status": "eq.approved",
                "price": "gt.0",
                "business.enabled": "eq.true",
                "business.is_test": "eq.false",
                "order": "updated_at.desc",
                "limit": str(_PAGE_SIZE),
                "offset": str(offset),
            },
            safe="!:,().",
        )
        return scrapy.Request(
            f"{_BASE}?{query}",
            headers={"apikey": _APIKEY, "Authorization": f"Bearer {_APIKEY}"},
            callback=self.parse_page,
            meta={"offset": offset},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning("marketplace_vu: non-JSON response at %s", response.url)
            return
        if not isinstance(products, list) or not products:
            return

        offset = response.meta["offset"]
        logger.info("marketplace_vu offset=%s count=%s", offset, len(products))
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            item = self._item(product, scraped_at)
            if item:
                yield item

        page = offset // _PAGE_SIZE
        if len(products) >= _PAGE_SIZE and page + 1 < _MAX_PAGES:
            yield self._request(offset + _PAGE_SIZE)

    def _item(self, product: dict, scraped_at: str):
        name = html.unescape(str(product.get("name") or "")).strip()
        price = product.get("price")
        if not name or price is None:
            return None

        business = product.get("business") or {}
        if self._hidden_by_shop_policy(product, business):
            return None

        category = self._label(product.get("category"))
        subcategory = self._label(product.get("subcategory"))
        category_text = " ".join(x for x in [category, subcategory] if x)
        if self._skip_category(category_text):
            return None

        shop = html.unescape(str(business.get("name") or "")).strip()
        category_parts = [x for x in [shop, category, subcategory] if x]
        product_id = str(product.get("id"))
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "brand": shop or None,
            "category": " > ".join(category_parts) if category_parts else None,
            "price": str(price),
            "currency": self.currency,
            "available": self._available(product),
            "url": f"https://app.marketplace.vu/customer/product-details?id={product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _label(value):
        if not isinstance(value, dict):
            return None
        label = value.get("name_language2") or value.get("name")
        if not label:
            return None
        return html.unescape(str(label)).strip()

    @staticmethod
    def _available(product: dict) -> bool:
        stock = product.get("stock_available")
        if stock is None:
            return True
        try:
            return float(stock) != 0
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _hidden_by_shop_policy(product: dict, business: dict) -> bool:
        price = product.get("price")
        stock = product.get("stock_available")
        try:
            if business.get("hide_zero_price_products") and float(price) <= 0:
                return True
        except (TypeError, ValueError):
            return True
        try:
            if business.get("hide_out_of_stock_products") and float(stock) == 0:
                return True
        except (TypeError, ValueError):
            return False
        return False

    @staticmethod
    def _skip_category(category_text: str) -> bool:
        folded = category_text.lower()
        return any(token in folded for token in _SKIP_CATEGORY_TOKENS)
