"""Guam Shopping Network -- https://www.guamshoppingnetwork.com/food.

First-party, cross-category storefront (auto/beauty/clothing/food/gadgets/
kids/kitchen/medical/pets/souvenirs) running on GrooveKart (a
PrestaShop-derived SaaS -- the session cookie is oddly named "thirtybees"
but every static asset loads from cdn.groovekart.com). Only the /food
category is in scope per the onboarding target. Prices are server-rendered
directly on the category listing (no PDP visit needed): each card is
li.product-box > h3.name a.gk_a_tag (name + url) with span.price-txt
containing span.old-price (regular) and/or span.reduced-price (sale).

Thin category: "Showing 1 - 6 of 6 items", no pagination control -- only 6
products total. Clears the >=5-row ship gate but only just; revisit if the
catalog doesn't grow."""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.guamshoppingnetwork.com/food"
_PRICE_RE = re.compile(r"[\d,]+\.\d{2}")


class GuamShoppingNetworkSpider(scrapy.Spider):
    name = "guamshoppingnetwork"
    allowed_domains = ["guamshoppingnetwork.com", "www.guamshoppingnetwork.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        cards = response.css("li.product-box, div.product-box")
        seen = set()
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            href = card.css("h3.name a.gk_a_tag::attr(href)").get()
            name = card.css("h3.name a.gk_a_tag::text").get()
            if not href or not name or href in seen:
                continue
            seen.add(href)
            price_text = (
                card.css("span.reduced-price::text").get()
                or card.css("span.old-price::text").get()
                or ""
            )
            m = _PRICE_RE.search(price_text)
            if not m:
                logger.warning("guamshoppingnetwork: no price for %s", href)
                continue
            slug = href.rstrip("/").split("/")[-1]
            product_id = slug.split("-", 1)[0] if slug[:1].isdigit() else slug
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "price": m.group(0).replace(",", ""),
                "currency": self.currency,
                "category": "food",
                "url": response.urljoin(href),
                "scraped_at": scraped_at,
            }
        logger.info("guamshoppingnetwork: %d unique products", len(seen))
