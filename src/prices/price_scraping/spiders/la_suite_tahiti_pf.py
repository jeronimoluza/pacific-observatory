"""La Suite Tahiti menu-touch menu prices."""

from price_scraping.spiders._static_cfp_menu import StaticCfpMenuSpider


class LaSuiteTahitiPfSpider(StaticCfpMenuSpider):
    name = "la_suite_tahiti_pf"
    allowed_domains = ["app.menu-touch.fr"]
    start_urls = ["https://app.menu-touch.fr/index.php?id_client=14560"]
    venue_name = "La Suite Tahiti"
    price_before_name = True
