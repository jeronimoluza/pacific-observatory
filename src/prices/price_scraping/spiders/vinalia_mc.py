"""Vinalia Monaco -- Odoo eCommerce wine / fine-grocery merchant.

Genuinely Monaco-domiciled (Monaco country-code phone +377 97701775, no
France/Monaco shared-platform question here since this is its own Odoo
instance, not a national chain deploy). Standard Odoo 17 website_sale
product grid; the visual pager is hidden by custom CSS
("navigation happens by scrolling, not buttons" per an Italian dev
comment found in the page's inline <style>) but the /page/N hrefs are
still present in the raw HTML, so Scrapy sees them even though a real
browser wouldn't show a clickable button.

/shop itself has a broken/hidden pager (a template expression
"as.ppg(5,)" renders literally, a sign of a misconfigured snippet) and
does not reliably enumerate the whole 718-item catalog, so this crawls
the 65 named categories instead (seeded as start_urls) and paginates
each with its own /page/N links -- confirmed disjoint on champagne-41
(page 1: 40 category-specific items; page 2: 37 new items; the ~5-7
item overlap on each page is a "you might also like" carousel, not a
pagination bug).
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_CATEGORY_SLUGS = [
    "appellations-regionales-127", "chablis-122", "champagne-41",
    "champagne-cote-de-sezanne-131", "champagne-cote-des-bar-aube-132",
    "champagne-cote-des-blancs-130", "champagne-montagne-de-reims-128",
    "champagne-vallee-de-la-marne-129", "cote-chalonnaise-125",
    "cote-de-beaune-124", "cote-de-nuits-123", "dispensa-3", "epicerie-fine-3",
    "epicerie-fine-charcuterie-aperitif-134",
    "epicerie-fine-charcuterie-aperitif-biscuits-sales-snacks-115",
    "epicerie-fine-charcuterie-aperitif-terrines-charcuterie-114",
    "epicerie-fine-sale-133", "epicerie-fine-sale-legumes-conserves-113",
    "epicerie-fine-sale-mer-riviere-110", "epicerie-fine-sale-pates-riz-111",
    "epicerie-fine-sale-sauces-huiles-condiments-112",
    "epicerie-fine-sale-truffes-champignons-109", "epicerie-fine-sucre-135",
    "epicerie-fine-sucre-chocolat-116", "epicerie-fine-sucre-confitures-miels-117",
    "epicerie-fine-sucre-douceurs-patisserie-118",
    "epicerie-fine-sucre-douceurs-patisserie-panettoni-119", "maconnais-126",
    "spiritueux-2", "spiritueux-amer-abv-54", "spiritueux-anise-55",
    "spiritueux-brandy-56", "spiritueux-calvados-57", "spiritueux-cognac-58",
    "spiritueux-gin-59", "spiritueux-liqueur-creme-60", "spiritueux-porto-61",
    "spiritueux-rhum-rum-62", "spiritueux-tequila-63", "spiritueux-vodka-64",
    "spiritueux-whisky-65", "vins-1", "vins-alsace-35", "vins-argentine-36",
    "vins-autriche-37", "vins-auvergne-102", "vins-beaujolais-38",
    "vins-bordeaux-39", "vins-bourgogne-40", "vins-espagne-42",
    "vins-italie-piemont-104", "vins-italie-pouilles-107",
    "vins-italie-sicile-106", "vins-italie-toscane-105",
    "vins-italie-venetie-108", "vins-jura-44", "vins-languedoc-45",
    "vins-loire-46", "vins-nouvelle-zelande-47", "vins-provence-48",
    "vins-rhone-nord-49", "vins-rhone-sud-50", "vins-savoie-51",
    "vins-slovaquie-52", "vins-usa-53",
]


class VinaliaMcSpider(scrapy.Spider):
    name = "vinalia_mc"
    allowed_domains = ["www.vinalia.mc", "vinalia.mc"]
    currency = "EUR"
    language = "fr"
    start_urls = [
        f"https://www.vinalia.mc/shop/category/{slug}" for slug in _CATEGORY_SLUGS
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "COOKIES_ENABLED": False,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = response.url.rsplit("/", 2)[-1].split("?")[0]
        if category == "" or category.isdigit():
            category = response.url.rstrip("/").rsplit("/", 1)[-1]
        for card in response.css("div.oe_product"):
            name = card.css("a.vinalia-card-name::text").get()
            url = card.css("a.vinalia-card-name::attr(href)").get() or card.css(
                "a.oe_product_image_link::attr(href)"
            ).get()
            price = card.css('[itemprop="price"]::text').get()
            price_currency = card.css('[itemprop="priceCurrency"]::text').get()
            product_id = card.css("input.product_ref_id::attr(value)").get()
            if not (name and url and price):
                continue
            yield {
                "product_id": product_id or url,
                "product_name": " ".join(name.split())[:500],
                "category": category,
                "price": f"{float(price):.2f}",
                "currency": price_currency or self.currency,
                "available": True,
                "url": urljoin(response.url, url),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for href in response.css('a[href*="/page/"]::attr(href)').getall():
            if href:
                yield response.follow(href, callback=self.parse)
