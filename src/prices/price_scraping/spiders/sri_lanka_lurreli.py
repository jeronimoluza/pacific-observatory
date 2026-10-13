"""Sri Lanka-local public Shopify product catalogue."""
import scrapy

from price_scraping.spiders._shopify_base import ShopifyBaseSpider

# lurreli.lk is now a Hydrogen storefront (/products.json 404s); the backing
# online store on the myshopify domain still serves the feed. Rows keep the
# public lurreli.lk URLs.
_API_BASE = "https://lurreli.myshopify.com"


class SriLankaLurreliSpider(ShopifyBaseSpider):
    name = "sri_lanka_lurreli"
    allowed_domains = ["lurreli.lk", "lurreli.myshopify.com"]
    base_url = "https://lurreli.lk"
    currency = "LKR"
    language = "en"

    def _to_api(self, request):
        return request.replace(url=request.url.replace(self.base_url, _API_BASE, 1))

    async def start(self):
        async for request in super().start():
            yield self._to_api(request)

    def parse_page(self, response):
        for out in super().parse_page(response):
            yield self._to_api(out) if isinstance(out, scrapy.Request) else out

    def _items(self, product):
        for item in super()._items(product):
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            item["country"] = 'Sri Lanka'
            item["sector"] = "consumer_goods"
            yield item
