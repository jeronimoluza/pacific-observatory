"""
Spider for Los Mejores Productos (Spain) —
https://losmejoresproductos.es/.

Independent price-tracking site with matched-product discipline (same
brand/format/size tracked across chains). No WAF (curl_cffi
impersonate="chrome124" clears with plain headers). WordPress/Astra site;
`/precios/` is an index of `<store>/<category>/` pages (122 pages across
carrefour/dia/mercadona re-verified 2026-09-06), each a server-rendered
HTML table (`table.lmp-ptable`) with one row per product:

    <tr><td class="rk">#</td>
        <td class="pd"><a href="/producto/<slug>/">
            <span class="tn"><span class="nm">NAME<span class="best-tag">
            ...</span></span></span></a></td>
        <td class="r tnum">SIZE</td>
        <td class="r tnum">€PRICE</td>
        <td class="r"><b class="tnum">€UNIT_PRICE/unit</b></td>
    </tr>

`span.nm`'s direct text node is the clean product name (the "mejor €/l"
best-tag is a nested sibling span, excluded by taking text() on `.nm`
itself rather than `.nm//text()`). Store and category come from the
listing page's own URL path, not from the row.

Re-verified live 2026-09-06: /precios/carrefour/aceite/ -> 200, 91
products, first row "Aceite de girasol para freir Carrefour garrafa 5 l."
€8,29 (€1,66/l).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://losmejoresproductos.es"
_CAT_LINK_RE = re.compile(
    r'href="(https://losmejoresproductos\.es/precios/[a-z]+/[a-z0-9-]+/)"'
)
_PRICE_RE = re.compile(r"([0-9]+,[0-9]{2})")


class LosmejoresproductosEsSpider(scrapy.Spider):
    name = "losmejoresproductos_es"
    allowed_domains = ["losmejoresproductos.es"]
    currency = "EUR"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/precios/", callback=self.parse_index)

    def parse_index(self, response):
        links = sorted(set(_CAT_LINK_RE.findall(response.text)))
        logger.info(f"losmejoresproductos_es: {len(links)} store/category pages")
        for url in links:
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        parts = response.url.rstrip("/").split("/")
        store, category = parts[-2], parts[-1]
        rows = response.xpath('//table[contains(@class,"lmp-ptable")]/tbody/tr')
        logger.info(
            f"losmejoresproductos_es: store={store} category={category} rows={len(rows)}"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            href = row.xpath('.//td[@class="pd"]/a/@href').get()
            name = row.xpath('.//td[@class="pd"]/a//span[@class="nm"]/text()').get()
            tds = row.xpath("./td")
            if not href or not name or len(tds) < 4:
                continue
            price_text = tds[3].xpath("string()").get() or ""
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": f"{store}/{category}",
                "price": m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": href,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
