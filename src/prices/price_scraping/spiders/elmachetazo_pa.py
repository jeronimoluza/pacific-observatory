"""El Machetazo (Panama) -- https://www.elmachetazo.com/. VTEX tenant, whole-catalog crawl.

Site's own JSON-LD declares priceCurrency USD (Panama circulates US dollar notes
alongside the PAB balboa at fixed 1:1 parity; countries.yaml declares PAB).
"""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class ElmachetazoPaSpider(VtexBaseSpider):
    name = "elmachetazo_pa"
    allowed_domains = ["elmachetazo.com"]
    HOST = "www.elmachetazo.com"
    currency = "USD"
    language = "es"
