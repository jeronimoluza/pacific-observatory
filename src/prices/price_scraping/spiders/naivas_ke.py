"""
Naivas Online — https://naivas.online/.

Largest Kenyan-owned supermarket chain. Corporate site naivas.info says
"Page Coming Soon" and links out — the real catalogue is naivas.online, a
server-rendered Laravel + Livewire (Webkul/Bagisto) storefront. Products are
NOT exposed via a JSON API; the homepage lists ~200 leaf category paths
(e.g. /cold-beverage/soda), and each leaf category page is fully
server-rendered HTML with real product cards — no JS execution required
(Tier 1A).

Each product card is a `<div class="h-full" wire:id="...">` container
holding: a hidden `<input name="product_id">`, a `<a title="...">` with the
product name, and a `.product-price span.font-bold` with the current price
("KES 179"); a second, struck-through span carries the pre-discount price
when the item is on offer but is not used here.

Pagination is `?page=N` (1-indexed, verified live 2026-08-31: page=1..N
return distinct product_id sets, e.g. breakfast/breakfast-cereals pages 1-5
returned 75 distinct ids with zero overlap) and terminates cleanly with a
page holding zero product cards (page 10 still had 15, page 20 had 0 on
that category) — walked as a counter until a page yields no cards, which is
a genuine end-of-catalog signal here, not a broken-pagination flat cap.

Currency KES confirmed in-page. Mixed grocery + household + electronics
catalogue; category slugs like breakfast-cereals, cold-beverage/soda,
canned-frozen-meals, cold-deli/cheese are food/beverage COICOP-relevant.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://naivas.online"
_PRICE_RE = re.compile(r"([\d,]+(?:\.\d{1,2})?)")


class NaivasKeSpider(scrapy.Spider):
    name = "naivas_ke"
    allowed_domains = ["naivas.online", "www.naivas.online"]
    currency = "KES"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_home, errback=self.errback
        )

    def parse_home(self, response):
        hrefs = sorted(
            set(
                response.css("nav a::attr(href), a::attr(href)").re(
                    r"^(?:https?://(?:www\.)?naivas\.online)?(/[a-z0-9\-]+/[a-z0-9\-]+)$"
                )
            )
        )
        leaf_categories = [h for h in hrefs if "deals" not in h]
        logger.info(f"{self.name}: leaf categories found={len(leaf_categories)}")
        for slug in leaf_categories:
            yield scrapy.Request(
                f"{BASE_URL}{slug}?page=1",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug.strip("/"), "page": 1},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        containers = response.xpath('//div[@class="h-full" and @*[name()="wire:id"]]')
        found = 0

        for card in containers:
            pid = card.css('input[name="product_id"]::attr(value)').get()
            name = (card.css("a[title]::attr(title)").get() or "").strip()
            raw_price = card.css(".product-price span.font-bold::text").get() or ""
            href = card.css('a[wire\\:click="redirectToProductPage"]::attr(href)').get()

            price_match = _PRICE_RE.search(raw_price.replace("\xa0", " "))
            if not pid or not name or not price_match:
                continue
            price = price_match.group(1).replace(",", "")
            if float(price) == 0:
                continue

            found += 1
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {response.url} category={category} page={page} "
            f"cards={len(containers)} yielded={found}"
        )

        if found > 0:
            next_page = page + 1
            yield scrapy.Request(
                f"{BASE_URL}/{category}?page={next_page}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": category, "page": next_page},
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
