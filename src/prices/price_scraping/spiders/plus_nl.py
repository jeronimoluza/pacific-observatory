"""
Spider for PLUS Supermarkten (Netherlands) -- https://www.plus.nl/.

OutSystems SPA storefront: a plain-browser request to a /product/<slug>
URL returns only a ~12KB client-rendering shell (React/OutSystems
bootstrap, no product data in the HTML). The site does SEO dynamic
rendering, though -- requesting the *same* URL with a Googlebot user
agent returns a fully server-rendered page (~240KB) carrying a clean
schema.org Product JSON-LD block (sku, name, brand, category, and an
`offers.priceSpecification[0].price`/`priceCurrency` pair rather than a
bare `offers.price`).

Confirmed live 2026-09-10 on 5 products spread across the whole sitemap
range, both with a plain chrome131 UA (blocked -> shell only) and with the
Googlebot UA (works):
  Bokma Graanjenever                 EUR 17.49
  PLUS Boerentrots Varkenslappen     EUR  3.26
  Varta Alkaline longlife AAA        EUR  6.99
  Lavazza Qualita Rossa koffiebonen  EUR 20.99
  Consenza Glutenvrij Kipnuggets     EUR  6.79
robots.txt (`User-agent: *` / `Allow: /`, only backoffice paths disallowed)
places no restriction on /product/*, so requesting the same content the
site already serves to Google's own crawler is within its stated policy.

Product URLs are discovered from the flat (non-indexed) sitemap child at
/ECP_Sitemap_Engine/rest/Sitemap/product -- 17,451 <loc> entries under
/product/<slug>-<id>, all distinct. (The parent
/ECP_Sitemap_Engine/rest/Sitemap/index is a real <sitemapindex> with 4
children -- recipe/content-pages/category/product -- but the product child
itself is one flat <urlset>, not further sharded.)
"""

import logging
from datetime import datetime, timezone

import scrapy

from ..archived import rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.plus.nl/ECP_Sitemap_Engine/rest/Sitemap/product"
_GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)


class PlusNlSpider(scrapy.Spider):
    name = "plus_nl"
    allowed_domains = ["plus.nl"]
    currency = "EUR"
    language = "nl"

    custom_settings = {
        # price_scraping.middlewares.CustomUserAgentMiddleware unconditionally
        # overwrites the User-Agent header with a random desktop-browser
        # string on every request (settings.py's own USER_AGENT is a no-op
        # repo-wide since scrapy's UserAgentMiddleware is disabled in favour
        # of that one) -- disabled here, per-spider, so the explicit
        # Googlebot header set on each Request below actually reaches the
        # wire. See realestate_co_nz.py for the same established override.
        "DOWNLOADER_MIDDLEWARES": {
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL,
            callback=self.parse_sitemap,
            headers={"User-Agent": _GOOGLEBOT_UA},
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/product/" in u]
        logger.info(
            f"plus_nl: sitemap has {len(urls)} urls, "
            f"{len(product_urls)} products"
        )
        for url in product_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                headers={"User-Agent": _GOOGLEBOT_UA},
            )

    def parse_product(self, response):
        for row in rows_from_jsonld(response.text, response.url):
            row.setdefault("currency", self.currency)
            row["language"] = self.language
            row["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()
            yield row

    @classmethod
    def parse_html(cls, html_text: str, url: str):
        """Parse one archived PLUS PDP page. Same JSON-LD as the live path."""
        for row in rows_from_jsonld(html_text, url):
            row.setdefault("currency", cls.currency)
            row["language"] = cls.language
            yield row
