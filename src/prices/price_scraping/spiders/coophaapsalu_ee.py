"""
Coop Haapsalu e-pood (Estonia) — https://coophaapsalu.ee/.

The candidate handed to this pass was ecoop.ee (Coop Estonia's national
portal), but that domain is a corporate/marketing site with no cart or
per-product prices -- it lists store locations and links out to
independently-run regional cooperatives' own e-shops (a Coop Estonia page
literally says "these are e-shops run by the regional cooperatives
themselves, so selection and delivery terms vary by region"). Of the
listed regional shops (a static map: Haapsalu -> its own e-shop; Tallinn/
Pärnu -> Wolt; Tartu -> Bolt Food), coophaapsalu.ee is the one genuine
first-party WooCommerce storefront; Wolt/Bolt are third-party delivery
marketplaces already handled by other sources. This spider targets that
real e-shop, resolving the candidate to the domain that actually carries
prices per the "supplied candidate list" disambiguation step (source_id
kept as ecoop.ee's regional match).

Verified live 2026-09-06: GET /wp-json/wc/store/v1/products?per_page=1
-> 200, X-WP-Total 10086. Standard WooCommerce Store API, no auth.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class CoophaapsaluEeSpider(WooBaseSpider):
    name = "coophaapsalu_ee"
    allowed_domains = ["coophaapsalu.ee"]
    currency = "EUR"
    language = "et"
    BASE_URL = "https://coophaapsalu.ee/wp-json/wc/store/v1/products"
