"""Second Hand Jersey (Channel Islands) -- https://secondhandjersey.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class SecondhandjerseyCiSpider(WooBaseSpider):
    name = "secondhandjersey_ci"
    allowed_domains = ["secondhandjersey.com"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://secondhandjersey.com/wp-json/wc/store/v1/products"
    # Store API reports the Jersey pound (JEP, at par with GBP); normalise to GBP.
    FORCE_CURRENCY = "GBP"
