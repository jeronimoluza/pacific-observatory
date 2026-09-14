"""Denmark-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class DenmarkJwareSpider(WooBaseSpider):
    name = "denmark_jware"
    allowed_domains = ["jware.dk"]
    BASE_URL = "https://jware.dk/wp-json/wc/store/v1/products"
    currency = "DKK"
    language = "da"
    PER_PAGE = 10


    # LiteSpeed serves challenge HTML to the project TLS impersonation. Its
    # public Store API returns JSON to this constrained plain-HTTP profile.
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "USER_AGENT": "Mozilla/5.0 (compatible; PriceSourceAudit/1.0)",
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": 500,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
            "scrapy.downloadermiddlewares.retry.RetryMiddleware": 590,
            "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750,
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }


    def _item(self, product):
        item = super()._item(product)
        if not item or not item.get("product_name"):
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        item["country"] = 'Denmark'
        item["sector"] = "consumer_goods"
        return item
