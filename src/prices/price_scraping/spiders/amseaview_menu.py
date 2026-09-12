"""AM SeaView Residence & Hotel (Paynesville, Liberia) -- restaurant and bar
menu, https://amseaviewresidence.com/

Prepared-food and beverage prices -- breakfast, seafood, pizza, sandwiches,
soft drinks, beer, wine, spirits, cocktails. That is COICOP 11.1 catering
(plus alcoholic-beverage-on-premises), a division retailer SKU catalogs
structurally cannot reach, which is why a hotel menu earns a manifest here.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124:
  * /restaurant_menu returns 200 with ~58 priced items already in the raw
    HTML -- a Next.js site, but server-rendered, so Tier 1A and no Playwright.
  * /sitemap.xml lists 16 pages; the menu items live on the dining/restaurant/
    bar pages. This spider walks the sitemap and parses every page, taking
    whatever menu rows each one holds, rather than hard-coding one path.
  * OVERLAP TRAP, measured 2026-09-12: /dining is the UNION of /restaurant and
    /bar -- 33 + 25 items reappear verbatim on it, so a naive sitemap walk
    emits 116 rows for 58 dishes and the url-anchor scheme below cannot
    collapse them (different page = different url = different url_hash), which
    would land the same dish in the corpus twice as two "products". The spider
    therefore dedupes on the dish NAME across the whole run, first occurrence
    wins. A dish that genuinely carried two prices on two pages would lose the
    second; on this menu none does.
  * Item markup:
        <h3 class="...">Breakfast</h3>
        <ul><li class="flex gap-4">
              <div class="flex-1"><p>Africa Breakfast</p><p>Boiled plantain,
                eddoes, yam, sweet potatoes, cassava &amp; smoked fish
                gravy</p></div>
              <span class="...text-gold">$10</span></li>

CURRENCY: USD, stated by the page itself -- "Prices are in US dollars and may
change". Recorded rather than assumed because Liberia is dual-currency. The
page also notes 13% GST is added to the final order, so these are pre-tax
menu prices; noted here so nobody later reads them as tax-inclusive.

Page family parsed: listing (menu pages).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


def _anchor(url: str, name: str) -> str:
    """Give every row on a one-page menu its own URL.

    The repo's DuplicationPipeline drops any item whose `url` it has already
    seen this run (md5 of the url string), so a menu where every dish shares
    the page URL collapses to ONE row -- measured here on 2026-09-12:
    item_scraped_count went to 1 with 14 dishes parsed. Appending a slug of the
    dish name as a fragment is both honest (it is an anchor into that page) and
    the right identity for a menu, where the dish name IS the product key.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{url}#{slug}" if slug else url

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_PRICE_RE = re.compile(r"^\s*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$")
_SITEMAP = "https://amseaviewresidence.com/sitemap.xml"


class AmseaviewMenuSpider(scrapy.Spider):
    name = "amseaview_menu"
    allowed_domains = ["amseaviewresidence.com", "www.amseaviewresidence.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_names: set[str] = set()

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if not u.endswith(".xml")]
        self.logger.info(f"{self.name}: {len(urls)} pages in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_menu)

    def parse_menu(self, response):
        n = 0
        for li in response.css("li"):
            span = li.css("span::text").getall()
            price = None
            for text in span:
                m = _PRICE_RE.match(text)
                if m:
                    price = m.group(1).replace(",", "")
                    break
            if not price:
                continue
            name = li.css("p::text").get()
            if not name:
                continue
            key = name.strip().casefold()
            if key in self._seen_names:
                continue  # /dining repeats /restaurant + /bar verbatim
            self._seen_names.add(key)
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            n += 1
            yield {
                "product_id": None,
                "product_name": name.strip()[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": _anchor(response.url, name.strip()),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        if n:
            self.logger.info(f"{self.name}: {n} menu rows from {response.url}")
