"""
J'Achete (Cote d'Ivoire) -- https://jachete.ci/.

Standard WooCommerce Store API on the versioned route
(/wp-json/wc/store/v1/products), zero auth. Broad general marketplace
(2231 SKUs total: electronics, appliances, auto parts, beauty, toys, ...).

Per the COICOP 01/02-only mandate for this onboarding pass, this spider is
SCOPED to a whitelist of food/drink category ids only -- it does not crawl
the non-food catalog (electronics/appliances/auto/beauty dominate the
unfiltered feed).

Categories confirmed live 2026-09-11 via
/wp-json/wc/store/v1/products/categories: Alimentaire (90, 161 items),
Alimentation (209, 34), Boisson (99, 114), Biere (101, 3), Grains et Riz
(91, 11), Huiles - Conserve (94, 22), Lait (103, 36), Condiment et
vinaigre (331, 61), Epicerie (330, 15), Cafe/The/Expresso (157, 45),
Alimentation bebe (96, 2), Biberon Alimentation (211, 3), Buvable (415, 1).
currency_minor_unit=0 (integer XOF, matches countries.yaml).
"""

import logging
from datetime import datetime, timezone

import scrapy

from price_scraping.spiders._woo_base import WooBaseSpider

logger = logging.getLogger(__name__)

_API = "https://jachete.ci/wp-json/wc/store/v1/products"
_PER_PAGE = 100

_FOOD_CATEGORY_IDS = {
    90: "Alimentaire",
    209: "Alimentation",
    99: "Boisson",
    101: "Biere",
    91: "Grains et Riz",
    94: "Huiles - Conserve",
    103: "Lait",
    331: "Condiment et vinaigre",
    330: "Epicerie",
    157: "Cafe, The & Expresso",
    96: "Alimentation bebe",
    211: "Biberon Alimentation",
    415: "Buvable",
}


class JacheteCiSpider(scrapy.Spider):
    name = "jachete_ci"
    allowed_domains = ["jachete.ci"]
    currency = "XOF"
    language = "fr"
    # Required by the reused WooBaseSpider._item() helper below.
    FORCE_CURRENCY = None
    PRICE_MULTIPLIER = 1
    PRICE_MULTIPLIER_CURRENCY = None

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        for cat_id, cat_name in _FOOD_CATEGORY_IDS.items():
            yield scrapy.Request(
                f"{_API}?category={cat_id}&per_page={_PER_PAGE}&page=1",
                callback=self.parse,
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": 1},
            )

    def parse(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]
        logger.info(f"{self.name}: cat={cat_name} page={page} got={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = WooBaseSpider._item(self, p)
            if item:
                item["scraped_at_utc"] = scraped_at
                yield item

        if len(products) >= _PER_PAGE:
            next_page = page + 1
            cat_id = response.meta["cat_id"]
            yield scrapy.Request(
                f"{_API}?category={cat_id}&per_page={_PER_PAGE}&page={next_page}",
                callback=self.parse,
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": next_page},
            )
