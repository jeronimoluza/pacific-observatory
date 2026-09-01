"""
Mabele Coop (Democratic Republic of Congo) — https://mabele-coop.com/.

Small Kinshasa "supermarché bio & produits locaux" cooperative. Next.js App
Router storefront: /produits is server-rendered (product cards present in
the raw HTML response body, not just the hydration payload), so this is a
Tier 1A HTML scrape — no API needed.

Probed live 2026-08-31: /produits returns exactly 12 distinct products
(confirmed via the embedded RSC `initialData` JSON as well as the visible
card markup) with no pagination — ?page=2 returns zero product cards, so
this is the whole catalogue, not a capped walk. 8 of 12 (67%) are food or
beverage (category "Aliments": dried bananas, 4 artisanal chocolate bars,
a granola-type pack; category "Boissons": 2 artisanal Congolese wines);
the remaining 4 are "Cosmétiques" (soaps). Prices are server-quoted in FC
(franc congolais) directly by this single merchant — not a multi-vendor
marketplace — so the kedomarket_cd-style per-row currency mislabelling
trap does not apply here; range observed 3,946-62,510 FC (~USD 1.4-22 at
~2,800 CDF/USD), plausible retail shelf prices, not the ~2,900x-under
mislabelling kedomarket_cd guards against.

Each product card is a `div.group` containing the name (h3), a link to
`/produits/<slug>` (used as both product_id and canonical URL), the
category label (span with the `tracking-[0.15em]` class — the only span
sharing `text-primary uppercase` that isn't the "Voir Détails" hover
badge), and the price (span text ending "FC", using U+202F narrow
no-break space as the thousands separator).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://mabele-coop.com"
START_URL = f"{BASE_URL}/produits"


class MabeleCoopCdSpider(scrapy.Spider):
    name = "mabele_coop_cd"
    allowed_domains = ["mabele-coop.com"]
    currency = "CDF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            START_URL, callback=self.parse_listing, errback=self.errback
        )

    def parse_listing(self, response):
        cards = response.css("div.group")
        found = 0
        seen_hrefs = set()

        for card in cards:
            href = card.css('a[href^="/produits/"]::attr(href)').get()
            name = card.css("h3::text").get()
            if not href or not name or href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            name = name.strip()

            price_text = None
            for span_text in card.css("span::text").getall():
                t = span_text.strip()
                if t.endswith("FC"):
                    price_text = t
                    break
            if not price_text:
                continue
            digits = re.sub(r"[^\d]", "", price_text)
            if not digits or int(digits) <= 0:
                continue

            category = (
                card.css('span[class*="tracking-[0.15em]"]::text').get() or ""
            ).strip() or None

            found += 1
            yield {
                "product_id": href.rsplit("/", 1)[-1],
                "product_name": name[:500],
                "category": category,
                "price": digits,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: {response.url} cards={len(cards)} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
