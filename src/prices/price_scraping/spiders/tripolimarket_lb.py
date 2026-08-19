"""Tripoli Market (Lebanon) -- https://tripolimarket.com/. General grocery/household
e-grocer in Tripoli, Lebanon. Prior round mislabeled this domain as "libya" (Tripoli is
also the name of Libya's capital) -- the site itself, phone country code (+961), and
LBP pricing confirm it is the Lebanese Tripoli. WooCommerce Store API is open
(no Cloudflare/PerimeterX block observed on this endpoint despite the fingerprint
sweep flagging both blockers on the homepage)."""

from price_scraping.spiders._woo_base import WooBaseSpider


class TripolimarketLbSpider(WooBaseSpider):
    name = "tripolimarket_lb"
    allowed_domains = ["tripolimarket.com"]
    currency = "LBP"
    language = "en"
    BASE_URL = "https://tripolimarket.com/wp-json/wc/store/v1/products"
