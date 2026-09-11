"""
Spider for Abidjan Market (Cote d'Ivoire) - abidjan-market.ci

Bespoke Symfony marketplace ("Portail" server header) aggregating small
Abidjan first-party sellers (`/boutiques/<slug>`). Fully server-rendered:
a plain GET on `/produits?page=N` returns product cards with name + XOF
price, and every PDP at `/produits/<slug>` carries name, price, category
badge and the add-to-cart form id. No JS, no WAF, no robots.txt (404).

Page family parsed: PDP (`/produits/<slug>`). Listing pages
(`/produits?page=N`) also carry name + price in the same markup and are
only used here as a URL source.
"""

import logging

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from price_scraping.selectors import get_selectors
from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)

BASE_URL = "https://abidjan-market.ci"


class AbidjanmarketCiSpider(CrawlSpider):
    name = "abidjanmarket_ci"
    allowed_domains = ["abidjan-market.ci"]
    currency = "XOF"
    language = "fr"

    # `/produits` paginates ~24 cards per page; page 1-8 covers the catalog
    # today and an over-run renders an empty grid rather than an error.
    start_urls = [f"{BASE_URL}/produits?page={p}" for p in range(1, 9)] + [
        f"{BASE_URL}/boutiques",
    ]

    SELECTORS = get_selectors("abidjanmarket_ci")

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    rules = (
        # PDPs: exactly one slug segment under /produits/. This excludes
        # /produits/categorie/<slug>, which carries a second segment.
        Rule(
            LinkExtractor(
                allow=r"/produits/[^/]+$",
                deny=r"(/panier|/connexion|/inscription|/mon-espace-vendeur|/pages/|/blog)",
            ),
            callback="parse_product",
            follow=False,
        ),
        # Seller storefronts and category pages, as extra PDP sources.
        Rule(
            LinkExtractor(allow=r"/(boutiques|produits/categorie)/[^/]+$"),
            follow=True,
        ),
    )

    @staticmethod
    def _breadcrumb(parts):
        """The category badge is rendered twice on a PDP; de-duplicate."""
        seen, out = set(), []
        for p in parts or []:
            p = (p or "").strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return " > ".join(out) or None

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": self._breadcrumb(category),
                "url": response.url,
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        else:
            logger.warning(f"Could not extract product data from {response.url}")
