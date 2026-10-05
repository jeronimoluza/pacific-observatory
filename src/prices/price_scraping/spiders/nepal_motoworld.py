"""Nepal-local public Woo product catalogue."""
from price_scraping.spiders._woo_base import WooBaseSpider


class NepalMotoworldSpider(WooBaseSpider):
    name = "nepal_motoworld"
    allowed_domains = ["motoworldnepal.com"]
    BASE_URL = "https://motoworldnepal.com/wp-json/wc/store/v1/products"
    currency = "NPR"
    language = "en"

    # WordPress.com's edge rejects this project's default Chrome 120 TLS
    # impersonation but accepts standard HTTP with a current browser UA.
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
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
        item["country"] = 'Nepal'
        item["sector"] = "consumer_goods"
        return item
