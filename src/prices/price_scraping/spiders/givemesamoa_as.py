"""GIVEMESAMOA Online (American Samoa) Shopify storefront."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider

_FOOD_WORDS = (
    "candy",
    "chocolate",
    "coffee",
    "food",
    "snack",
    "treat",
)


class GivemesamoaAsSpider(ShopifyBaseSpider):
    name = "givemesamoa_as"
    allowed_domains = ["givemesamoa.com"]
    base_url = "https://givemesamoa.com"
    currency = "USD"
    language = "en"

    def _items(self, p: dict):
        text = " ".join(
            str(v or "")
            for v in (
                p.get("title"),
                p.get("product_type"),
                " ".join(p.get("tags") or []),
            )
        ).lower()
        if any(word in text for word in _FOOD_WORDS):
            return
        for item in super()._items(p):
            if item.get("available"):
                yield item
