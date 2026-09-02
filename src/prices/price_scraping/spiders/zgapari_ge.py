"""
Spider for Zgapari (Georgia) -- https://online.zgapari.ge/.

Zgapari ("ზღაპარი") is a 25-branch Tbilisi supermarket chain, independent
from Europroduct (different company, different Facebook page) but running
the SAME custom storefront platform as europroduct_ge -- identical CSS
class names (product-grid-item / js-product-item / product-name /
product-price / add-to-cart-btn). Unlike Europroduct, the /products
listing here is NOT category-chunked: a single flat walk over
/products, /products/page-2/, ... /products/page-97/ (confirmed live,
zero product_id overlap between page 1 and page 2) covers the whole
catalog, so no category ids are needed.

Re-verified live 2026-09-01: GET /products -> 200, ~104KB, 12 distinct
product cards per page e.g. 'ბრინჯი გრძელი/ჩვენი სუფრა/900გ' (rice) with a
sale price 2,95 GEL / regular 3,79 GEL. Prices use the Lari sign (₾),
matches countries.yaml GEL. Product IDs come from the PDP URL
(/products/product/<ID>), not a data-id attribute on the card itself.

Each product card:
<div class="product-grid-item js-product-item ">
  <div class="img-wrap"><a href=".../products/product/<ID>" .../></div>
  <div class="info-wrap">
    <h4 class="product-name"><a href=".../products/product/<ID>">NAME</a></h4>
    <span class="product-price">
      <span class="new">PRICE ₾</span><span class="old">PRICE ₾</span>
    </span>
    (or, no discount:) <span class="product-price"><span>PRICE ₾</span></span>
  </div>
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://online.zgapari.ge"
MAX_PAGES = 150  # safety cap; catalog measured at 97 pages live

_CARD_RE = re.compile(
    r'class="product-grid-item js-product-item[^"]*"[^>]*>.*?'
    r'<h4 class="product-name">\s*<a[^>]*href="[^"]*/products/product/([0-9A-Za-z]+)"[^>]*>'
    r"([^<]+)</a>.*?"
    r'<span class="product-price">\s*(?:<span class="new">([^<]+)</span>'
    r"|<span>([^<]+)</span>)",
    re.S,
)


class ZgapariGeSpider(scrapy.Spider):
    name = "zgapari_ge"
    allowed_domains = ["online.zgapari.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/products",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"zgapari_ge: page={page} cards={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, name, new_price, plain_price in cards:
            price = new_price or plain_price
            price = price.replace("₾", "").strip().replace(",", ".")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/products/product/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/products/page-{nxt}/",
                callback=self.parse_page,
                meta={"page": nxt},
            )
