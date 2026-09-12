"""Xpress It Liberia -- https://www.xpressliberia.com/

Monrovia multi-vendor online shop (Laravel/Apache, own storefront code). The
catalog is genuinely mixed local retail: groceries and drinks, cosmetics and
personal care, household goods, and vendor-branded items (e.g. "J2J
Supplies").

Probed live 2026-09-12 with curl_cffi impersonate=chrome124:
  * Server-rendered HTML, prices in the markup -- Tier 1A, no Playwright.
  * /shop paginates on `?page=N` and page 1 / page 2 / page 3 return DIFFERENT
    product-id sets (18 / 14 / 20 distinct ids), so the listing is genuinely
    enumerable rather than one fixed page.
  * TRAP measured on this tenant: a "featured products" block is re-rendered
    at the top of EVERY page, before the `<h2>All Products</h2>` heading, so a
    naive card-level parse double-counts the same few SKUs once per page. The
    grid under `section.products-section-modern` is the paginated one; this
    spider takes cards only from that section and additionally dedupes on the
    product id across the run.

Card markup:
    <a href="/shop/product/<id>" class="product-card-link">
      <h3 class="product-card-title">Kojie San Kojic Acid Soap 2 Bars</h3>
      <span class="price-current">$20.00</span>

CURRENCY: USD -- prices render with a bare "$" and no machine-readable
currency code anywhere on the page. Liberia is dual-currency (USD/LRD), and
"$" is ambiguous there, so this is a judgement call recorded explicitly: the
site's own copy and its vendor pages quote US dollars.

Page family parsed: listing (/shop?page=N). PDPs exist at /shop/product/<id>
but render the same card markup for related products, which is why the listing
is the safer family here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_BASE = "https://www.xpressliberia.com"
_MAX_PAGES = 200
_ID_RE = re.compile(r"/shop/product/(\d+)")


class XpressLiberiaSpider(scrapy.Spider):
    name = "xpress_liberia"
    allowed_domains = ["xpressliberia.com", "www.xpressliberia.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen: set[str] = set()

    async def start(self):
        yield scrapy.Request(f"{_BASE}/shop?page=1", callback=self.parse_list,
                             meta={"page": 1})

    def parse_list(self, response):
        page = response.meta["page"]
        grid = response.css("section.products-section-modern")
        cards = grid.css("a.product-card-link")
        new = 0
        for card in cards:
            href = card.attrib.get("href", "")
            m = _ID_RE.search(href)
            pid = m.group(1) if m else href
            if pid in self._seen:
                continue
            self._seen.add(pid)
            name = card.css("h3.product-card-title::text").get()
            price = card.css("span.price-current::text").get()
            if not name or not price:
                continue
            price = price.strip().lstrip("$").replace(",", "")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            new += 1
            yield {
                "product_id": m.group(1) if m else None,
                "product_name": name.strip()[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": response.urljoin(href),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        self.logger.info(
            f"{self.name}: page={page} cards={len(cards)} new={new}"
        )
        if new and page < _MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/shop?page={page + 1}",
                callback=self.parse_list,
                meta={"page": page + 1},
            )
