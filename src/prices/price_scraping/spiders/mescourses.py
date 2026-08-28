"""Spider for Mescourses (Madagascar) -- https://mescourses.mg/ (rebrand of
supermarche.mg, same investor-backed Antananarivo operator; supermarche.mg
302-redirects here)."""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class MescoursesSpider(PrestashopBaseSpider):
    name = "mescourses"
    allowed_domains = ["mescourses.mg"]
    currency = "MGA"
    language = "fr"
    HOME_URL = "https://mescourses.mg/fr/"
