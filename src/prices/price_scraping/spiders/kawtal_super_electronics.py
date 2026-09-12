"""Kawtal Super Electronics -- https://kawtalsuperelectronics.online/

Small Monrovia phone/electronics shop ("Electronics shop in Monrovia,
Liberia" in its own copy). Catalog is genuinely small: the /shop page states
"6 products", and 6 is what this spider yields -- enough to clear the >=5-row
bar, and recorded here so nobody later reads a 6-row run as a broken spider.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124: the product grid
is client-rendered, BUT the /shop page also server-renders a plain SEO list of
every product as anchors carrying the name and price inline:

    <li><a href="/product/<uuid>">iPhone XS Max 256GB &mdash; $250.00</a></li>

That list is the whole catalog, which is why this needs no Playwright and no
API. The site's /sitemap.xml carries only 5 static pages and NO product URLs,
so the sitemap route does not work here.

CURRENCY: USD. Prices render as a bare "$" with no machine-readable code;
Liberia is dual-currency, and phone retail in Monrovia is dollarized.
Judgement call, recorded not assumed.

Page family parsed: listing (/shop SEO anchor list).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_URL = "https://kawtalsuperelectronics.online/shop"
# "iPhone XS Max 256GB — $250.00"  (em dash, occasionally a hyphen)
_ITEM_RE = re.compile(r"^(.*?)\s*[—–-]\s*\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$")


class KawtalSuperElectronicsSpider(scrapy.Spider):
    name = "kawtal_super_electronics"
    allowed_domains = ["kawtalsuperelectronics.online"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_shop)

    def parse_shop(self, response):
        seen = set()
        for a in response.css('a[href^="/product/"]'):
            href = a.attrib.get("href", "")
            text = " ".join(t.strip() for t in a.css("::text").getall()).strip()
            m = _ITEM_RE.match(text)
            if not m:
                continue
            name, price = m.group(1).strip(), m.group(2).replace(",", "")
            if not name or href in seen:
                continue
            seen.add(href)
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            yield {
                "product_id": href.rsplit("/", 1)[-1],
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": response.urljoin(href),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        self.logger.info(f"{self.name}: {len(seen)} products from {response.url}")
