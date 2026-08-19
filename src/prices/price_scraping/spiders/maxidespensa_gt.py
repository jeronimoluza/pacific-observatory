"""MaxiDespensa (Guatemala) -- https://www.maxidespensa.com.gt/. Bodega-format Walmart Centroamerica banner, fresh produce confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class MaxidespensaGtSpider(VtexBaseSpider):
    name = "maxidespensa_gt"
    allowed_domains = ["maxidespensa.com.gt"]
    HOST = "www.maxidespensa.com.gt"
    currency = "GTQ"
    language = "es"
