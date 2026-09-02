"""
Spider for Delikateska.ru (Russia) — https://delikateska.ru/, a Moscow
specialty-grocery / delicatessen retailer ("интернет магазин продуктов и
деликатесов" — online store of groceries and delicacies): caviar, farm
meat/dairy, imported cheeses, seafood, plus a full staple-grocery taxonomy
(dairy, meat, bread, vegetables/fruit, groceries, drinks).

Server-rendered React storefront (no city/store cookie required — checked
cold). /catalog lists ~53 top-level category slugs; each category page
embeds its product grid directly in raw HTML as `.product-card-new` anchor
cards (the anchor itself carries the `/product/<id>` href). Name is a plain
text node (`.product-card-new__title`); price is split across a text node
for whole rubles and a `.product-card-new__price__decimal` span for the
kopecks fraction on discounted items (e.g. "139" + ",99"), so it's read via
`.product-card-new__price ::text` (descendant combinator) rather than the
non-recursive `::text` pseudo-element, and re-joined before parsing.

No working pagination was found on this platform — `?page=N` and `/N`
suffixes both 404 or re-serve an empty shell, and each category page tops
out at its full first-screen grid (observed 20-31 cards per category, no
"show more"/next control in the raw HTML). Treated as each category's full
listed assortment rather than a capped page; a future pass could confirm
via a network trace whether more loads on scroll.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://delikateska.ru"
CATALOG_INDEX = f"{BASE_URL}/catalog"

_PRODUCT_ID_RE = re.compile(r"/product/(\d+)")


class DelikateskaRuSpider(scrapy.Spider):
    name = "delikateska_ru"
    allowed_domains = ["delikateska.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        # A handful of category requests come back 403 at concurrency=4 /
        # 0.5s delay (simple burst-throttling, not a hard WAF -- clears at
        # lower concurrency); RETRY_TIMES covers the rest.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            CATALOG_INDEX, callback=self.parse_index, errback=self.errback
        )

    def parse_index(self, response):
        hrefs = sorted(set(response.css('a[href^="/catalog/"]::attr(href)').getall()))
        categories = sorted({h for h in hrefs if re.match(r"^/catalog/[a-z0-9-]+$", h)})
        logger.info(f"{self.name}: categories found={len(categories)}")
        for href in categories:
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            yield response.follow(
                href,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        cards = response.css(".product-card-new")
        found = 0

        for card in cards:
            href = card.attrib.get("href") or card.css("::attr(href)").get() or ""
            id_match = _PRODUCT_ID_RE.search(href)
            if not id_match:
                continue

            name = (card.css(".product-card-new__title::text").get() or "").strip()
            price = self._extract_price(card)
            if not name or price is None:
                continue

            found += 1
            yield {
                "product_id": id_match.group(1),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {response.url} category={category} "
            f"cards={len(cards)} yielded={found}"
        )

    @staticmethod
    def _extract_price(card):
        # ::text alone only grabs the price block's direct text node ("139"),
        # missing the kopecks fraction nested in a child <span> (",99") on
        # discounted items — the descendant combinator picks up both parts.
        parts = card.css(".product-card-new__price ::text").getall()
        if not parts:
            return None
        raw = "".join(parts).replace("\xa0", "").replace("₽", "").strip()
        raw = raw.replace(",", ".")
        match = re.match(r"([\d.]+)", raw)
        if not match:
            return None
        amount = match.group(1)
        try:
            if float(amount) <= 0:
                return None
        except ValueError:
            return None
        return amount

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
