"""Spider for Supermarche Galerie TATA (Mauritania) -- http://galerietata.com/.
Plain HTTP: the site's TLS cert doesn't match the hostname."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class GalerietataSpider(PrestashopBaseSpider):
    name = "galerietata"
    allowed_domains = ["galerietata.com"]
    currency = "MRU"
    language = "fr"
    HOME_URL = "http://galerietata.com/"
