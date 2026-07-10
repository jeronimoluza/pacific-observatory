"""
Spider for scraping South Star Drug (Philippines) - https://southstardrug.com.ph/
Extracts product information including prices, categories, and URLs.

The site migrated to a client-side-rendered Next.js App Router SPA: every
page returns HTTP 200 with an empty static shell (no product markup, no
__NEXT_DATA__) and hydrates product cards via an encrypted `/api/proxy`
endpoint that can't be replayed directly. Requests are routed through
Playwright (`meta['playwright']=True` + `wait_until='networkidle'`) so the
hydrated DOM is captured, then product cards are parsed directly off the
category listing pages (name + price + url all live on the card — no need
to visit individual product pages). Category routes are a fixed ~30-item
grid with no pagination/load-more control.
"""

import logging

import scrapy

logger = logging.getLogger(__name__)


class SouthStarDrugSpider(scrapy.Spider):
    """
    Spider for South Star Drug (Philippines).
    Renders each category listing page via Playwright and parses product
    cards directly (name + price + url).
    """

    name = "south_star_drug"
    allowed_domains = ["southstardrug.com.ph"]
    start_urls = [
        "https://southstardrug.com.ph/product-lists/medicines",
        "https://southstardrug.com.ph/product-lists/groceries",
        "https://southstardrug.com.ph/product-lists/medical-supplies-and-equipments",
        "https://southstardrug.com.ph/product-lists/mom-and-baby",
        "https://southstardrug.com.ph/product-lists/exclusive-brands",
    ]
    currency = "PHP"

    CARD_XPATH = '//div[contains(@class, "shadow-lg") and contains(@class, "peer-checked:bg-blue-100")]'
    NAME_XPATH = './/div[contains(@class, "line-clamp-3")]/text()'
    PRICE_XPATH = './/div[contains(@class, "font-semibold")]//span/text()'
    URL_XPATH = './/a[contains(@href, "/products/")]/@href'

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "networkidle"},
                },
                callback=self.parse_listing,
            )

    def parse_listing(self, response):
        """Parse product cards directly off the hydrated category listing page."""
        cards = response.xpath(self.CARD_XPATH)
        if not cards:
            logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            name = card.xpath(self.NAME_XPATH).get()
            price = card.xpath(self.PRICE_XPATH).get()
            href = card.xpath(self.URL_XPATH).get()

            if name and price:
                yield {
                    "product_name": name.strip(),
                    "category": None,
                    "price": price.strip(),
                    "currency": self.currency,
                    "url": response.urljoin(href) if href else response.url,
                    "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
                }
            else:
                logger.warning(f"Could not extract product data from a card on {response.url}")
