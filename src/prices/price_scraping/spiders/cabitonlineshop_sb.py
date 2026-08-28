"""
Spider for CAB'IT Online Shop (Solomon Islands) -- take.app/cabitonlineshop

Take.app is a shared Next.js storefront SaaS platform used by multiple
independent merchants (this store, its sibling CAB'IT Foody, and at least
one Brunei storefront onboarded separately). The platform is server-rendered
-- no Playwright/API needed -- Tier 1A.

Platform pattern (generalizes to every take.app storefront):
  - Store home: https://take.app/<store_alias>
  - Category listing (server-rendered, has product cards):
        https://take.app/<store_alias>/c/<category_id>
  - Product detail: https://take.app/<store_alias>/p/<product_id>
Category ids are discovered from `/c/<id>` links on the store home page.
Each category page's product cards are `<a href=".../p/<id>">` anchors
containing an `<img alt="<product name>">` and a sibling `<p>$<price></p>`
(both wrapped in content-hashed CSS module class names -- not usable as
selectors, hence the regex-on-anchor-HTML approach below instead of CSS
class selectors). Name+price live directly in the category listing; no PDP
visit is needed. Currency is read from the store's own `country`/`currency`
metadata during probing (SBD for Solomon Islands stores) rather than parsed
from the "$" glyph, which is ambiguous across take.app tenants.
"""

import html as html_lib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ALT_RE = re.compile(r'alt="([^"]*)"')
_PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


class CabitonlineshopSbSpider(scrapy.Spider):
    name = "cabitonlineshop_sb"
    allowed_domains = ["take.app"]
    currency = "SBD"
    language = "en"
    STORE_ALIAS = "cabitonlineshop"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"https://take.app/{self.STORE_ALIAS}", callback=self.parse
        )

    def parse(self, response):
        cat_ids = sorted(
            set(
                re.findall(
                    rf"https://take\.app/{self.STORE_ALIAS}/c/([a-zA-Z0-9]+)",
                    response.text,
                )
            )
        )
        logger.info(f"{self.name}: found {len(cat_ids)} categories")
        for cid in cat_ids:
            yield scrapy.Request(
                f"https://take.app/{self.STORE_ALIAS}/c/{cid}",
                callback=self.parse_category,
            )

    def parse_category(self, response):
        title = response.css("title::text").get() or ""
        category = title.split(" - ")[0].strip() or None

        seen_ids: set[str] = set()
        cards = response.css(f'a[href*="/{self.STORE_ALIAS}/p/"]')
        for card in cards:
            href = card.attrib.get("href", "")
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            outer = card.get()
            alt_m = _ALT_RE.search(outer)
            price_m = _PRICE_RE.search(outer)
            if not (alt_m and price_m):
                continue

            product_name = html_lib.unescape(alt_m.group(1)).strip()
            price = price_m.group(1).replace(",", "")
            if not product_name or not price:
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": href,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"Scraped product: {product_name}")
