"""Super Xtra (Panama) -- https://www.superxtra.com/. VTEX tenant, whole-catalog crawl.

Panama circulates US dollar notes alongside the PAB balboa at fixed 1:1 parity
(countries.yaml declares PAB); priced in USD on-site.
"""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SuperxtraPaSpider(VtexBaseSpider):
    name = "superxtra_pa"
    allowed_domains = ["superxtra.com"]
    HOST = "www.superxtra.com"
    currency = "USD"
    language = "es"
