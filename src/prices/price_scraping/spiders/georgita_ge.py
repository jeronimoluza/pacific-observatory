"""
Spider for Georgita (Georgia) -- https://georgita.ge/en/.

Custom ASP.NET/IIS storefront. The `/en/shop` landing page is a static
"inspiration" banner shell with no product grid and no XHR calls
(confirmed via Playwright network trace 2026-09-06) -- category browsing
does not go through a discoverable API here.

Instead this spider walks the 1,536 English PDP urls listed directly in
`sitemap.xml` (`/en/products/product/<hex-id>`, a hashed id, not
sequential -- no id-walk possible, the sitemap is the only enumeration).
Each PDP server-renders the product's own name/price/category as plain
text, no JSON-LD and no client-side fetch needed:

  <h1 class="product-name">CARCHELEJO-SALAMI EXTRA WHITE TRIPE...</h1>
  <span class="product-price"><span>7.20 &#8382;</span></span>
  <div class="text-wrap product-text">
    <b> Category : </b>Meat and fish<br><b> Brand : </b>CARCHELEJO<br>...

Confirmed live 2026-09-06: /en/products/product/DA14CAEE4D -> 200,
"CARCHELEJO-SALAMI EXTRA WHITE TRIPE,GLUTEN FREE 2.5KG" GEL 7.20
(currency symbol on-page is the Georgian Lari sign U+20BE, mapped to ISO
GEL). The PDP also lists 3-4 "related products" further down the page
with their own `<span class="product-price"><span class="new">...`
markup (discounted-price style, `class="new"`) -- the extraction anchors
on the FIRST plain (non-`new`) product-price span, which is always the
page's own product, to avoid picking up a related item's price instead.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://georgita.ge"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(https://georgita\.ge/en/products/product/[A-F0-9]+)</loc>")
_NAME_RE = re.compile(r'<h1 class="product-name">([^<]+)</h1>')
_PRICE_RE = re.compile(
    r'<span class="product-price">\s*<span>\s*([\d.,]+)\s*₾\s*</span>', re.DOTALL
)
_CATEGORY_RE = re.compile(r"Category\s*:\s*</b>\s*([^<]+?)\s*<br")
MAX_PRODUCTS = 4000  # safety cap; full sitemap is 1,536 -- never actually hit


class GeorgitaGeSpider(scrapy.Spider):
    name = "georgita_ge"
    allowed_domains = ["georgita.ge"]
    currency = "GEL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"georgita_ge: sitemap yielded {len(urls)} product urls")
        for url in urls[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        name_m = _NAME_RE.search(response.text)
        price_m = _PRICE_RE.search(response.text)
        if not name_m or not price_m:
            logger.warning(f"georgita_ge: could not extract from {response.url}")
            return
        cat_m = _CATEGORY_RE.search(response.text)
        yield {
            "product_id": response.url.rsplit("/", 1)[-1],
            "product_name": name_m.group(1).strip()[:500],
            "category": cat_m.group(1).strip() if cat_m else None,
            "price": price_m.group(1).replace(",", "."),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
