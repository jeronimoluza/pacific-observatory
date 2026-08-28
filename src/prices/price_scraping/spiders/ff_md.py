"""FF.md (Moldova) -- https://ff.md/. Online pharmacy (supplements, OTC, RX).
Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FfMdSpider(ShopifyBaseSpider):
    name = "ff_md"
    allowed_domains = ["ff.md"]
    base_url = "https://ff.md"
    currency = "MDL"
    language = "ro"
