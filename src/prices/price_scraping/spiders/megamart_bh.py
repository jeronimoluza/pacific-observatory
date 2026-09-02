"""
MegaMart (Bahrain) — https://megamart.bh/. Online supermarket ("Grocery
Delivery Bahrain | Online Supermarket").

Server-rendered Django (django-oscar storefront: `/en/catalogue/...` URLs,
`static/oscar/js/...` asset paths) — confirmed live 2026-09-01 with plain
curl_cffi (impersonate=chrome124), no Playwright needed.

Category listing pages (`/en/catalogue/category/<path>_<id>/`, paginated
via `?page=N`) render product cards directly — name, price, and PDP url are
all in the listing HTML, so this spider never needs to visit a PDP:

    <div class="img" href="/en/catalogue/<slug>_<id>/">
      <img alt="<product name>" ...>
    ...
    <span class="currency">BD</span> <span class="intiger">11</span>
    <span class="decimal">.110</span>

Each category page also states its own total ("You've Viewed 99 of 395
Products"), used to compute how many `?page=N` requests to issue. Confirmed
enumerable, not a carousel: baby-diapers page 1 vs page 2 returned disjoint
product-id sets.

Category seed list (501 category/subcategory URLs) is scraped from the
homepage nav, which lists every department down to the leaf level —
parent and child category pages both list their products, so the same
product appears on more than one category page; DuplicationPipeline
collapses on `url`, which is stable per product (the slug+id in the PDP
href), so re-visits are harmless.

Currency: BHD, 3 decimals (e.g. "0.550" for Almarai Natural Hummus 250g,
confirmed against the live PDP) — matches the known BHD-is-a-3-decimal
GCC-currency trap (same family as JOD/KWD/OMR).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://megamart.bh"
PAGE_SIZE = 99  # observed "X of Y Products" step size
MAX_PAGES_PER_CATEGORY = 30  # safety cap
_CATEGORY_URL_RE = re.compile(r'href="(/en/catalogue/category/[^"]+_\d+/?)"')
_CARD_SPLIT = 'class="img" href="'
_HREF_ID_RE = re.compile(r"_(\d+)/?$")
_TOTAL_RE = re.compile(r"of\s+([\d,]+)\s+Products", re.I)


class MegamartBhSpider(scrapy.Spider):
    name = "megamart_bh"
    allowed_domains = ["megamart.bh"]
    currency = "BHD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE_URL}/en/", callback=self.parse_home)

    def parse_home(self, response):
        cat_paths = sorted(set(_CATEGORY_URL_RE.findall(response.text)))
        logger.info(f"megamart_bh: {len(cat_paths)} category URLs discovered")
        for path in cat_paths:
            yield scrapy.Request(
                f"{BASE_URL}{path}",
                callback=self.parse_category,
                meta={"category_path": path, "page": 1},
            )

    def parse_category(self, response):
        page = response.meta["page"]
        category_path = response.meta["category_path"]
        found = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for chunk in response.text.split(_CARD_SPLIT)[1:]:
            href = chunk.split('"', 1)[0]
            window = chunk[:2500]
            m_name = re.search(r'alt="([^"]+)"', window)
            m_int = re.search(r'class="intiger">(\d*)<', window)
            m_dec = re.search(r'class="decimal">\.?(\d*)<', window)
            if not (m_name and m_int and m_dec and m_int.group(1) and m_dec.group(1)):
                continue
            m_id = _HREF_ID_RE.search(href)
            if not m_id:
                continue
            found += 1
            yield {
                "product_id": m_id.group(1),
                "product_name": m_name.group(1).strip()[:500],
                "category": category_path.strip("/").split("/")[-1].rsplit("_", 1)[0],
                "price": f"{m_int.group(1)}.{m_dec.group(1)}",
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}{href}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        m_total = _TOTAL_RE.search(response.text)
        total = int(m_total.group(1).replace(",", "")) if m_total else 0
        logger.info(
            f"megamart_bh: {category_path} page={page} cards={found} total={total}"
        )

        max_page = min(MAX_PAGES_PER_CATEGORY, -(-total // PAGE_SIZE) if total else 1)
        if found and page < max_page:
            yield scrapy.Request(
                f"{BASE_URL}{category_path}?page={page + 1}",
                callback=self.parse_category,
                meta={"category_path": category_path, "page": page + 1},
            )
