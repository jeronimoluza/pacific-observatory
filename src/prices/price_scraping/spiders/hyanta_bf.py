"""
Spider for Hyanta (Burkina Faso) - https://www.hyanta.com/

Fresh-market grocery delivery based in Ouagadougou ("Marché de fruits et
légumes, Livraison partout au Burkina Faso"). Small static PHP storefront
(no anti-bot, no JS hydration needed) -- verified live 2026-09-01: ~65
products across 5 categories, each paginated via
grid.php?idcat=<id>&numpage=<n>:
  idcat=2  Fruits
  idcat=3  Légumes
  idcat=4  Feuilles et épices
  idcat=6  Viandes et poissons (incl. Volaille, Poulet de chair,
           Charcuterie, Faux filets subcategories -- all link to idcat=6)
  idcat=30 Divers / Packs (overlaps some idcat=6 product IDs as bundles --
           harmless, DuplicationPipeline dedups on `url`)

The Rule follows every `grid.php?idcat=<id>(&numpage=<n>)?` link it finds
on any crawled page, not just the 5 seeded above -- this also picked up
idcat=31/32 (a couple more products reachable only from a cross-category
widget) without needing to enumerate every id by hand.

Everything needed is already on the LISTING page -- no PDP visit required:
each real product card (`li.item.col-lg-4` -- the plain `li.item` class
alone also matches unrelated mega-menu `<li>` entries) carries
`div.item-category` (the real category, unlike the PDP's own "<h2>Page
title (Fruit)</h2>", which is a site bug that always says "Fruit"
regardless of actual category -- confirmed on idproduit=50, a poultry item,
still showing "(Fruit)" on its PDP), the product name in
`div.item-title a::attr(title)`, and price in `span.price::text`.

Some product names are served double-UTF-8-encoded by the site itself (raw
response bytes already contain "Ã©" where "é" belongs -- confirmed via a
raw byte dump, not a decoding bug on the scraper's side). `_fix_mojibake`
repairs this via encode-latin1/decode-utf-8, applied only when the tell-tale
"Ã" byte sequence is present so already-clean names are left untouched.

CURRENCY: XOF, no minor unit (e.g. "500 FCFA" = 500 XOF).
"""

import logging
import re
from datetime import datetime, timezone

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)


def _fix_mojibake(text: str | None) -> str | None:
    if not text or "Ã" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


class HyantaBfSpider(CrawlSpider):
    name = "hyanta_bf"
    allowed_domains = ["hyanta.com"]
    start_urls = [
        "https://www.hyanta.com/grid.php?idcat=2",
        "https://www.hyanta.com/grid.php?idcat=3",
        "https://www.hyanta.com/grid.php?idcat=4",
        "https://www.hyanta.com/grid.php?idcat=6",
        "https://www.hyanta.com/grid.php?idcat=30",
    ]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    rules = (
        Rule(
            LinkExtractor(allow=r"grid\.php\?idcat=\d+(&numpage=\d+)?$"),
            callback="parse_listing",
            follow=True,
        ),
    )

    @staticmethod
    def _parse_price(text: str | None) -> float | None:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return None
        return float(digits)

    def parse_start_url(self, response):
        return self.parse_listing(response)

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("li.item.col-lg-4")
        if not cards:
            logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            category = _fix_mojibake(
                (card.css("div.item-category::text").get() or "").strip() or None
            )
            name_raw = card.css("div.item-title a::attr(title)").get()
            product_name = _fix_mojibake((name_raw or "").strip()) or None
            price_text = card.css("span.price::text").get()
            price = self._parse_price(price_text)

            href = card.css("a.product-image::attr(href)").get()
            m = re.search(r"idproduit=(\d+)", href or "")
            product_id = m.group(1) if m else None
            url = (
                response.urljoin(f"product-detail.php?idproduit={product_id}")
                if product_id
                else None
            )

            if not product_name or price is None or not url:
                logger.warning(
                    f"Could not extract product data from a card on {response.url}"
                )
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"Scraped {len(cards)} product cards from {response.url}")
