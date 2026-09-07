"""La Dolce Vita Noumea menu prices."""

from price_scraping.spiders._static_cfp_menu import StaticCfpMenuSpider


class LaDolceVitaNcSpider(StaticCfpMenuSpider):
    name = "la_dolce_vita_nc"
    allowed_domains = ["ladolcevita.nc"]
    start_urls = ["https://ladolcevita.nc/la-carte/"]
    venue_name = "La Dolce Vita"
    price_before_name = False
