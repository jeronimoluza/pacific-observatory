"""
Spider for Choithrams (Sierra Leone) via the 247bigmarket.com marketplace.

Choithrams is a Freetown-headquartered supermarket chain. It has no
storefront of its own; it sells through the "247bigmarket.com" WooCommerce +
multi-vendor-marketplace platform (Sierra Leone's own online marketplace,
Dokan/MVX-style) as two named vendor stores:

  - /store/freetown/  -- Choithrams Freetown (19A Wellington Industrial
    Estate, 14 Rawdon Street, Freetown, Sierra Leone)
  - /store/kenema/    -- Choithrams Kenema

Per onboarding-skill guidance, a named supermarket behind a marketplace/
delivery-app front end counts as a supermarket source in its own right (same
pattern as the *_wolt_* sources) -- this is NOT the 247bigmarket marketplace
catalog itself (which would be channel: marketplace and excluded from the
food count). The other two vendors on this same marketplace
(icroyale, skbuildingmaterials) are NOT Choithrams and are out of scope for
this spider.

The vendor storefront ("/store/<slug>/", paginated "/store/<slug>/page/N/")
is server-rendered plain WooCommerce shop-loop HTML -- no JS, no WAF, no
special UA needed. Each product card on the listing page already carries
name + price + category + product id, so this spider parses the listing
pages directly rather than visiting each product detail page.

CURRENCY: the site prices everything in USD (WooCommerce Store API confirms
`currency_code: "USD"`, and the HTML price markup uses "$"). This is a
foreign-currency source for a country whose own currency is SLE -- flagged
per the onboarding brief's locality rule. It is a genuine, real shelf price
paid by Freetown customers on this platform (dollarized retail pricing is
not uncommon in Sierra Leone given SLE volatility), not a diaspora storefront
shipping internationally -- the vendor address is a real Freetown location
and 247bigmarket is Sierra Leone's own marketplace, not a foreign platform.
No SLL/SLE redenomination ambiguity applies since the site was never priced
in leones at all.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"[\d,]+\.?\d*")


class ChoithramsSlSpider(scrapy.Spider):
    name = "choithrams_sl"
    allowed_domains = ["247bigmarket.com"]
    currency = "USD"
    language = "en"

    STORE_SLUGS = ["freetown", "kenema"]
    MAX_PAGES_PER_STORE = 30  # safety cap; real catalogs are ~4 pages each

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        for slug in self.STORE_SLUGS:
            url = f"https://247bigmarket.com/store/{slug}/"
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "store_slug": slug,
                    "page_num": 1,
                    "handle_httpstatus_list": [404],
                },
                errback=self.errback,
            )

    def parse(self, response):
        store_slug = response.meta["store_slug"]
        page_num = response.meta["page_num"]

        if response.status == 404:
            logger.info(f"[{store_slug}] page {page_num}: 404, stopping pagination")
            return

        cards = response.css("div.prod_hold")
        if not cards:
            logger.info(f"[{store_slug}] page {page_num}: no product cards, stopping")
            return

        n_items = 0
        for card in cards:
            item = self._parse_card(card, response, store_slug)
            if item:
                n_items += 1
                yield item
        logger.info(f"[{store_slug}] page {page_num}: {n_items} items")

        if page_num < self.MAX_PAGES_PER_STORE and n_items > 0:
            next_page = page_num + 1
            next_url = f"https://247bigmarket.com/store/{store_slug}/page/{next_page}/"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={
                    "store_slug": store_slug,
                    "page_num": next_page,
                    "handle_httpstatus_list": [404],
                },
                errback=self.errback,
            )

    def _parse_card(self, card, response, store_slug):
        name = card.css("span.name::text").get()
        if not name:
            return None
        name = name.strip()

        price_text = " ".join(card.css("div.price_hold *::text").getall())
        m = _PRICE_RE.search(price_text.replace(",", ""))
        if not m:
            return None
        try:
            price = float(m.group(0))
        except ValueError:
            return None

        product_id = card.css("a.add_to_cart_button::attr(data-product_id)").get()
        url = card.css("a.wrap_link::attr(href)").get()
        if url:
            url = response.urljoin(url)
        else:
            url = response.url

        category = None
        card_classes = card.attrib.get("class", "")
        cat_m = re.search(r"product_cat-([a-z0-9-]+)", card_classes)
        if cat_m:
            category = cat_m.group(1).replace("-", " ")

        return {
            "product_id": product_id or url,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
