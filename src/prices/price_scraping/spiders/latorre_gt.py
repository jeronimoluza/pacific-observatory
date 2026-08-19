"""La Torre (Guatemala) -- https://www.latorre.com.gt/. Premium GT chain, full-line."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class LatorreGtSpider(VtexBaseSpider):
    name = "latorre_gt"
    allowed_domains = ["latorre.com.gt"]
    HOST = "www.latorre.com.gt"
    currency = "GTQ"
    language = "es"
