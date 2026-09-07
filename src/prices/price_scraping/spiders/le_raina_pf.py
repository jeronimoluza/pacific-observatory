"""Le Raina Papeete menu prices."""

from price_scraping.spiders._static_cfp_menu import StaticCfpMenuSpider


class LeRainaPfSpider(StaticCfpMenuSpider):
    name = "le_raina_pf"
    allowed_domains = ["leraina.com", "www.leraina.com"]
    start_urls = ["https://www.leraina.com/en/menus/"]
    venue_name = "Le Raina"
    price_before_name = False
