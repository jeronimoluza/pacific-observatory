"""
Shared base class for Watsons Asia/EAP spiders.

Watsons runs the same Angular SSR storefront across at least 7 EAP countries
(SG, HK, TH, MY, PH, ID, TW). All sit behind AkamaiGHost and serve identical
PDP markup:
  <wtc-product-price-summary>...<div class="display-price">
    <span>{CURRENCY_SYMBOL}</span><span class="price">9.24</span>
  </div>...

Curl_cffi with chrome120 TLS impersonation (via scrapy-impersonate) bypasses
the WAF. Each country has the same /sitemap.xml -> /sitemap_prd_{lang}_NN.xml
discovery pattern, with TW being the only outlier (no `en` sitemap, only zh_TW).

Subclasses override seven attributes (name/allowed_domains/currency/language/
SITEMAP_INDEX/SITEMAP_FILTER/PRICE_SYMBOL); everything else is inherited.

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import scrapy

logger = logging.getLogger(__name__)

LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
ID_RE = re.compile(r"/p/(BP_\d+)")


class WatsonsBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language,
    # SITEMAP_INDEX, SITEMAP_FILTER, PRICE_SYMBOL.
    name = None
    IMPERSONATE_PROFILE = "chrome120"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    SITEMAP_INDEX: str = ""
    SITEMAP_FILTER: str = "sitemap_prd_en"
    PRICE_SYMBOL: str = ""

    def start_requests(self):
        yield scrapy.Request(
            self.SITEMAP_INDEX,
            callback=self.parse_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_index(self, response):
        for loc in LOC_RE.findall(response.text):
            if self.SITEMAP_FILTER in loc:
                yield scrapy.Request(
                    loc,
                    callback=self.parse_product_sitemap,
                    meta={"impersonate": self.IMPERSONATE_PROFILE},
                )

    def parse_product_sitemap(self, response):
        urls = LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        body = response.text

        name = self._extract_name(response, body)
        if not name:
            return

        price = self._extract_price(response, body)
        if not price:
            return

        m = ID_RE.search(response.url)
        product_id = m.group(1) if m else response.url

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": self._extract_category(body),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_name(self, response, body: str) -> str | None:
        og = response.xpath('//meta[@property="og:title"]/@content').get()
        if og:
            return og.strip()
        h1 = response.xpath("//h1//text()").get()
        if h1:
            return h1.strip()
        m = re.search(r"<title>([^<|]+)", body)
        return m.group(1).strip() if m else None

    def _extract_price(self, response, body: str) -> str | None:
        sale = response.xpath(
            '//div[contains(@class, "display-price") '
            'and not(contains(@class, "recommended"))]'
            '//span[contains(concat(" ", normalize-space(@class), " "), " price ")]/text()'
        ).get()
        if sale:
            sale = sale.strip()
            if re.match(r"^\d+(?:[\.,]\d+)?$", sale):
                return (
                    sale.replace(",", ".") if "," in sale and "." not in sale else sale
                )
        m = re.search(r'"lowPrice":\s*([0-9]+(?:\.[0-9]+)?)', body)
        if m:
            return m.group(1)
        m = re.search(r'"price":\s*([0-9]+(?:\.[0-9]+)?)', body)
        if m:
            return m.group(1)
        if self.PRICE_SYMBOL:
            pat = re.escape(self.PRICE_SYMBOL) + r"\s*([0-9]+(?:[,.][0-9]+)?)"
            m = re.search(pat, body)
            if m:
                return (
                    m.group(1).replace(",", ".")
                    if "," in m.group(1) and "." not in m.group(1)
                    else m.group(1)
                )
        return None

    def _extract_category(self, body: str) -> str | None:
        for m in re.finditer(
            r"<script[^>]*application/ld\+json[^>]*>\s*(\[.*?\]|\{.*?\})\s*</script>",
            body,
            re.DOTALL,
        ):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    data = next(
                        (
                            d
                            for d in data
                            if isinstance(d, dict)
                            and d.get("@type") == "BreadcrumbList"
                        ),
                        None,
                    )
                if isinstance(data, dict) and data.get("@type") == "BreadcrumbList":
                    items = data.get("itemListElement", [])
                    names = [
                        (i.get("item") or {}).get("name") or i.get("name")
                        for i in items
                        if isinstance(i, dict)
                    ]
                    names = [unquote(n) for n in names if n and n != "Home"]
                    if names:
                        return " > ".join(names[:3])
            except Exception:
                continue
        return None
