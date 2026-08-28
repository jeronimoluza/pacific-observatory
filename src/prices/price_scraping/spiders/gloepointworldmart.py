"""
Spider for Gloepoint World Mart (Brunei) - take.app storefront

Take.app (Next.js/Vercel SaaS) server-renders its storefront HTML, so a
plain HTTP fetch of the store root already contains every product card as
real <a>/<p> DOM nodes (no client-side JS execution or Playwright needed).
Each product card is an anchor whose href contains "/p/<product_id>";
within it, two paragraphs carrying class "mantine-focus-auto" hold
[product_name, price_with_$_prefix] in that order. Currency is embedded
in the page payload as a machine-readable "currency":"BND" field -
verified against the rendered $-prices, which are BND (Brunei Dollar),
never USD, per Brunei-market convention.

This pattern generalizes to other take.app/<store-slug> storefronts.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"([\d,.]+)")


class GloepointworldmartSpider(scrapy.Spider):
    name = "gloepointworldmart"
    allowed_domains = ["take.app"]
    currency = "BND"
    language = "en"

    STORE_SLUG = "gloepointworldmart"

    async def start(self):
        yield scrapy.Request(
            f"https://take.app/{self.STORE_SLUG}",
            callback=self.parse_listing,
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in response.css('a[href*="/p/"]'):
            href = card.attrib.get("href") or ""
            if f"/{self.STORE_SLUG}/p/" not in href:
                continue

            texts = card.css("p.mantine-focus-auto::text").getall()
            if len(texts) < 2:
                continue
            name, price_text = texts[0].strip(), texts[1].strip()

            m = PRICE_RE.search(price_text.replace(",", ""))
            if not name or not m:
                logger.debug(f"no name/price for card {href}")
                continue

            product_id = href.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": None,
                "price": m.group(1),
                "currency": self.currency,
                "url": href,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
