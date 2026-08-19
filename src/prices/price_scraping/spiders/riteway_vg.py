"""
Spider for RiteWay Food Markets (British Virgin Islands) —
https://www.riteway.vg/shop-groceries.html.

Magento 2 ("Roadtown" theme) SSR HTML; /graphql 404s via the Varnish edge
(module disabled) but the category listing page carries full name+price in
plain markup, so this reads it directly with standard ?p=N pagination.
"""

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider


class RitewayVgSpider(MagentoSSRBaseSpider):
    name = "riteway_vg"
    allowed_domains = ["riteway.vg"]
    currency = "USD"
    language = "en"

    START_URLS = ["https://www.riteway.vg/shop-groceries.html"]
    PAGE_PARAM = "p"
