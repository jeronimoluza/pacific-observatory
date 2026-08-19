"""Coursesnet (Algeria) — https://coursesnet.dz/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class CoursesnetDzSpider(WooBaseSpider):
    name = "coursesnet_dz"
    allowed_domains = ["coursesnet.dz", "www.coursesnet.dz"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://coursesnet.dz/wp-json/wc/store/v1/products"
