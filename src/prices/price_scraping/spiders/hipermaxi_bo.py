"""
Hipermaxi (Bolivia, largest supermarket chain) — https://www.hipermaxi.com/.

Next.js storefront, single representative branch used throughout
(santa-cruz/hipermaxi-roca-y-coronado). Category grid pages
(/categoria/<slug>) return HTTP 200 under plain curl_cffi but carry ZERO
product links in the server-rendered HTML — the grid hydrates client-side
against a catalog API that sits behind Radware Bot Manager (confirmed via
Playwright network trace: an `api.hcaptcha.com/checksiteconfig` call keyed
to `validate.perfdrive.com`, Radware's bot-management domain, fires on
category-page load). That API was out of scope for this pass.

The homepage, however, DOES server-render real product tiles (~54 distinct
/producto/ links across many departments: dairy, beverages, meat, cleaning,
snacks) — likely a "popular products" rail. Each product page itself is
plain server-rendered HTML with a clean schema.org Product JSON-LD block
(name, sku, offers.price, offers.priceCurrency=BOB), no auth or JS needed.

This spider seeds from the homepage's product links and does not attempt
the category grid. It is therefore a curated ~54-SKU subset, not a full
catalog walk — see the YAML notes for what a follow-up pass would need
(reverse-engineer or Playwright-render the Radware-protected category API).

Currency: BOB (matches countries.yaml and offers.priceCurrency on every
product probed).
"""

import json
import logging
import re

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://www.hipermaxi.com"
BRANCH_PATH = "/santa-cruz/hipermaxi-roca-y-coronado"
_PRODUCT_LINK_RE = re.compile(re.escape(BRANCH_PATH) + r"/producto/[^\"'\s]+")


class HipermaxiBoSpider(scrapy.Spider):
    name = "hipermaxi_bo"
    allowed_domains = ["hipermaxi.com"]
    currency = "BOB"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE}{BRANCH_PATH}", callback=self.parse_home)

    def parse_home(self, response):
        links = sorted(set(_PRODUCT_LINK_RE.findall(response.text)))
        logger.info(f"{self.name}: found {len(links)} product links on homepage")
        for link in links:
            yield scrapy.Request(f"{BASE}{link}", callback=self.parse_product)

    def parse_product(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            text = script.string or script.get_text()
            if not text:
                continue
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("@type") != "Product":
                continue
            item = self._item(data, response.url)
            if item:
                yield item
            return
        logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")

    def _item(self, data, url):
        name = data.get("name")
        offers = data.get("offers") or {}
        price = offers.get("price")
        if not name or price in (None, ""):
            return None
        try:
            if float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        return {
            "product_id": str(data.get("sku") or ""),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offers.get("availability") or "InStock"),
            "url": url,
            "language": self.language,
        }
