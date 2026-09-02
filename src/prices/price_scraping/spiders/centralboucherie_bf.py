"""
Spider for CentralBusiness / CentralBoucherie (Burkina Faso) -
https://www.centralboucherie.com/boutique

Specialty butcher / fine-grocery shop based in Balkui, Ouagadougou
("L'excellence de la boucherie et de l'epicerie fine au Burkina Faso").
Custom-built (non-platform) storefront -- the entire ~51-product catalog
(Boeuf, Mouton/Chevre, Charcuterie, Epices, fruits de mer, Volailles) is
rendered on the single /boutique listing page, verified live 2026-09-01.
Product cards have no plain <a href> to their detail page -- the PDP URL
only appears in an `onclick="window.location='...'"` attribute on the
`div.product-name` element -- so this spider extracts name/price/category/
url directly from the listing page rather than following links via
LinkExtractor (which would find nothing).

CURRENCY TRAP: prices use a space as the thousands separator, e.g.
"36 000 FCFA" is 36,000 XOF, not 36. All whitespace (incl. the frequent
non-breaking-space rendering of French thousands separators) is stripped
before the digits are parsed.

Out-of-stock items still show their price (e.g. "Escalope" 5,000 XOF) but
carry a "BIENTOT DE RETOUR" ribbon and a disabled `button.add-cart-btn`
whose text reads "Epuise" instead of "AJOUTER AU PANIER" -- both flagged
via that button's disabled attribute so `available` reflects real stock,
not just whether a price was shown.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ONCLICK_URL_RE = re.compile(r"window\.location='([^']+)'")


class CentralboucherieBfSpider(scrapy.Spider):
    name = "centralboucherie_bf"
    allowed_domains = ["centralboucherie.com"]
    start_urls = ["https://www.centralboucherie.com/boutique"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    @staticmethod
    def _parse_price(text: str | None) -> float | None:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return None
        return float(digits)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.product-card")
        if not cards:
            logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            name_div = card.css("div.product-name")
            product_name = (name_div.css("::text").get() or "").strip()
            onclick = name_div.attrib.get("onclick", "")
            m = _ONCLICK_URL_RE.search(onclick)
            url = m.group(1) if m else response.url

            price_text = card.css("div.product-price::text").get()
            price = self._parse_price(price_text)

            category = card.css("span.badge-cat::text").get()
            category = category.strip() if category else None

            if not product_name or price is None:
                logger.warning(
                    f"Could not extract product data from a card on {response.url}"
                )
                continue

            # Slug carries a short hex suffix the site itself appends
            # (e.g. "basse-cote-69c83f92b4e0a") -- use it as product_id
            # since there is no separate SKU field on the listing page.
            product_id = url.rstrip("/").rsplit("/", 1)[-1] if url else None

            available = not card.css("button.add-cart-btn[disabled]")

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": available,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"Scraped {len(cards)} product cards from {response.url}")
