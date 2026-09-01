"""
Spider for Super Selectos (El Salvador) -- https://www.superselectos.com/.

Independent Salvadoran chain operated by Calleja, S.A. de C.V. (confirmed
via site footer, 2026-09-01) -- NOT a Walmart Centroamerica banner, so no
product_id overlap risk with walmart_sv (different platform entirely:
ASP.NET Blazor Server here vs VTEX for walmart_sv).

IMPORTANT DEFECT, confirmed live 2026-09-01: the `?category=<code>` query
param on `/products` is decorative, not a real filter. Verified three ways:
(1) a persistent session (cookies incl. BranchOfficeIdselectos) returns the
same small pool of items regardless of the category code requested; (2) a
real Playwright click on a category link ("Cerveza premium") still lands
on the same generic item pool as "Yogurts"; (3) unrelated category codes
(e.g. "093300 Toallas humedas") return batteries/chocolate/wine, not wet
wipes. So `category` is NOT a reliable dimension here -- this spider does
not attempt to label it and instead emits `category: null` per the "leave
it null rather than invent one" rule.

What IS real: `&page=N` genuinely changes the returned product set (a
"Pagina X de Y" counter is present and page 2 differs from page 1), and
the underlying pool is much larger than any single page -- 20 varied
category+page fetches surfaced 232 distinct product IDs, so this behaves
like a large, paginated "recommended products" feed that ignores the
category filter rather than a fixed static block. The spider walks many
(category-code, page) seeds to sample broadly across that feed and relies
on Scrapy's url-based DuplicationPipeline to collapse repeats -- so the
`url` field is normalized to the canonical `?productId=<id>` form (the
same form the homepage's own product-name links use) rather than the
category-page-specific href, which otherwise varies per seed for the same
product and would defeat the dedup.

Category codes are seeded from the ~50 codes with real
`href="/products?category=<code>"` links embedded in homepage
featured-category widgets (confirmed spanning food and non-food alike:
"01634 Yogurts", "03695 Atun", "055181 Refrescos", "086264 Cremas
dentales"). The site's actual full category tree ("Todas las Categorias"
flyout) is Blazor/SignalR-interactive with no hrefs and unreachable via
plain HTTP.

El Salvador is dollarized; prices render as "$8.31" -> USD, matching
countries.yaml.
"""

import html as html_lib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.superselectos.com"
_CATEGORY_RE = re.compile(r'/products\?category=(\w+)">([^<]+)</a>')
_PAGE_LABEL_RE = re.compile(r"gina \d+ de (\d+)")
_MAX_PAGES_SAFETY = 40


class SuperselectosSvSpider(scrapy.Spider):
    name = "superselectos_sv"
    allowed_domains = ["superselectos.com"]
    currency = "USD"
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
        yield scrapy.Request(f"{_BASE}/", callback=self.parse_home)

    def parse_home(self, response):
        codes = sorted(set(code for code, _ in _CATEGORY_RE.findall(response.text)))
        logger.info(f"{self.name}: discovered {len(codes)} category seeds")
        for code in codes:
            yield scrapy.Request(
                f"{_BASE}/products?category={code}&page=1",
                callback=self.parse_listing,
                cb_kwargs={"code": code, "page": 1},
            )

    def parse_listing(self, response, code, page):
        for card in response.css("div.producto-box"):
            item = self._item(card)
            if item:
                yield item

        if page == 1:
            m = _PAGE_LABEL_RE.search(response.text)
            total_pages = int(m.group(1)) if m else 1
            total_pages = min(total_pages, _MAX_PAGES_SAFETY)
            for next_page in range(2, total_pages + 1):
                yield scrapy.Request(
                    f"{_BASE}/products?category={code}&page={next_page}",
                    callback=self.parse_listing,
                    cb_kwargs={"code": code, "page": next_page},
                )

    def _item(self, card):
        name = card.css("h5.prod-nombre a.clickeable::text").get()
        href = card.css("h5.prod-nombre a.clickeable::attr(href)").get()
        price = card.css("strong.precio::text").get()
        if not href or not name or not price:
            return None
        price = re.sub(r"[^\d.]", "", price)
        if not price:
            return None
        pid_match = re.search(r"productId=(\d+)", href)
        if not pid_match:
            return None
        product_id = pid_match.group(1)
        return {
            "product_id": product_id,
            "product_name": re.sub(r"\s+", " ", html_lib.unescape(name)).strip()[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/?productId={product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
