"""Boutikobf tangible-goods marketplace with alimentation/homepage fallbacks."""
from __future__ import annotations
import logging, re
from datetime import datetime, timezone
import scrapy

logger = logging.getLogger(__name__)
_START = ["https://www.boutikobf.com/marketplace?category=alimentation", "https://www.boutikobf.com/", "https://www.boutikobf.com/marketplace"]
_PRICE = re.compile(r"([0-9][0-9\s,.]*)\s*(?:FCFA|CFA|XOF)", re.I)
_COUNT = re.compile(r"(?:produits?|products?)\s*[:(]?\s*(\d+)|(\d+)\s*(?:produits?|products?)", re.I)
_SERVICE = re.compile(r"\b(service|prestation|formation|livraison|location|réparation|reparation|emploi|consult)\b", re.I)
def clean(v): return " ".join((v or "").replace("\\xa0", " ").split())
def price(v):
    m = _PRICE.search(clean(v))
    if not m:
        return None
    amount = m.group(1).replace(" ", "").replace(",", "")
    return amount if float(amount) >= 100 else None

class BurkinaFasoBoutikobfMarketplaceSpider(scrapy.Spider):
    name = "burkina_faso_boutikobf_marketplace"
    allowed_domains = ["www.boutikobf.com", "boutikobf.com"]
    start_urls = _START
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        cards = response.css("article, .listing, .product, .card, [class*='product'], [class*='listing']")
        claimed = self._claimed_count(response.text)
        accepted = 0
        for card in cards:
            text = clean(card.get())
            name = clean(card.css("h2::text, h3::text, .title::text, [class*='title']::text").get())
            value = price(text)
            if not (name and value and float(value) > 0) or _SERVICE.search(name): continue
            href = card.css("a::attr(href)").get()
            vendor = clean(card.css("[class*='vendor']::text, [class*='shop']::text, [class*='seller']::text").get()) or None
            locality = clean(card.css("[class*='location']::text, [class*='quartier']::text").get()) or "Ouagadougou"
            key = "|".join((name.casefold(), value, (vendor or "").casefold(), locality.casefold()))
            if key in getattr(self, "_seen", set()): continue
            self._seen = getattr(self, "_seen", set()) | {key}; accepted += 1
            yield {"product_id": key, "product_name": name[:500], "price": value, "currency": "XOF",
                   "country": "Burkina Faso", "vendor": vendor, "locality": locality,
                   "url": response.urljoin(href) if href else response.url, "scraped_at_utc": datetime.now(timezone.utc).isoformat()}
        if claimed and claimed > accepted:
            logger.warning("[%s] claimed %d listings but extracted %d tangible unique rows; cache/filter divergence possible", response.url, claimed, accepted)
        next_url = response.css("a[rel='next']::attr(href), .pagination .next::attr(href)").get()
        if next_url: yield response.follow(next_url, self.parse)

    @staticmethod
    def _claimed_count(text):
        m = _COUNT.search(clean(text)); return int(m.group(1) or m.group(2)) if m else None
