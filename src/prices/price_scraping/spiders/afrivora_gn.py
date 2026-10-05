"""Guinea food listings from Afrivora's public marketplace.

Afrivora is a multi-country classifieds marketplace.  The unfiltered site may
default to another country, so collection is deliberately limited to its food
route with the explicit ``country=GN`` query.  Cards are rendered by Next.js
after page load; Scrapy's normal HTTP response does not reliably contain them.

The source contains negotiable and obviously placeholder-like amounts.  This
spider therefore keeps only non-negotiable cards with an explicit FG/GNF price
of at least 1,000 GNF.  The project classifier remains responsible for
rejecting miscategorised non-food listings within Afrivora's food section.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_START_URL = "https://www.afrivora.com/fr/food?country=GN"
_CARD_SEL = 'a[href^="/fr/food/"]'
_ID_RE = re.compile(r"/fr/food/([0-9a-f-]{36})(?:[/?#]|$)", re.IGNORECASE)
_PRICE_RE = re.compile(r"([\d\s\u00a0\u202f,.]+)\s*(?:FG|GNF)\b", re.IGNORECASE)


def _parse_price(text: str) -> str | None:
    match = _PRICE_RE.search(text or "")
    if not match:
        return None
    amount = re.sub(r"[\s\u00a0\u202f,]", "", match.group(1)).rstrip(".")
    if not amount.isdigit():
        return None
    value = int(amount)
    if value < 1_000:
        return None
    return str(value)


class AfrivoraGnSpider(scrapy.Spider):
    name = "afrivora_gn"
    allowed_domains = ["afrivora.com", "www.afrivora.com"]
    currency = "GNF"
    language = "fr"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    async def start(self):
        yield scrapy.Request(
            _START_URL,
            callback=self.parse_listing,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", _CARD_SEL, timeout=20000),
                    PageMethod("wait_for_timeout", 1200),
                ],
            },
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen_ids: set[str] = set()
        yielded = 0

        for card in response.css(_CARD_SEL):
            href = card.attrib.get("href", "")
            id_match = _ID_RE.search(href)
            if not id_match:
                continue
            product_id = id_match.group(1).lower()
            if product_id in seen_ids:
                continue

            card_text = " ".join(card.css("*::text").getall()).strip()
            if "Nég." in card_text or "Contacter pour le prix" in card_text:
                continue

            name = (card.css("h3::text").get() or "").strip()
            price = _parse_price(card_text)
            location = " ".join(
                text.strip() for text in card.css("span::text").getall() if text.strip()
            )
            if not name or not price:
                continue
            if "Guinée" not in location:
                continue

            seen_ids.add(product_id)
            yielded += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "food",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info("afrivora_gn: rendered_cards=%d yielded=%d", len(response.css(_CARD_SEL)), yielded)

