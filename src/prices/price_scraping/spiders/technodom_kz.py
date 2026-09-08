"""
Spider for Technodom Kazakhstan — https://www.technodom.kz/.

Next.js SSR storefront. Category pages
(https://www.technodom.kz/catalog/<dept>/<subdept>) embed the full product
list for that page in a `<script id="__NEXT_DATA__">` JSON blob at
`props.pageProps.initialState.productList`, no Playwright needed and no
separate API call.

Re-verified live 2026-09-06: GET
/catalog/smartfony-i-gadzhety/smartfony-i-telefony/smartfony -> 200, 1.7MB,
`productList.items` has 24 SKUs of 482 total across 21 pages
(`paginationData.totalPages`). `?page=2` on the same path returns a disjoint
SKU set (confirmed pagination is real, not a cached single page). Sample:
sku 293876 'Смартфон Apple iPhone 17 Pro Max 12/256GB/6.9/48 Silver' price
871990 KZT.

`airba.kz` (a related P4 candidate, same triage sheet) now DNS/redirects
straight to this same www.technodom.kz — the "Airba Fresh" grocery storefront
the triage AI_NOTES described no longer exists.

Categories below are the 17 top-level department seeds pulled from
https://www.technodom.kz/categories-server-sitemap.xml (one representative
subcategory per department to keep the crawl from becoming an all-482-page
electronics-only walk while still spanning most COICOP divisions Technodom
actually carries: electronics/appliances, furniture/household, personal
care, sport, auto, kids, tools).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.technodom.kz"

_CATEGORIES = [
    "smartfony-i-gadzhety/smartfony-i-telefony",
    "fototehnika-i-kvadrokoptery/jekshn-kamery-i-aksessuary/jekshn-kamery",
    "tv-audio-foto-video/audio-tehnika/besprovodnye-kolonki",
    "avtotovary-i-transport/akkumuljatory-i-zarjadnye-ustrojstva/avtomobil-nye-zarjadnye-ustrojstva",
    "noutbuki-i-komp-jutery/noutbuki-i-aksessuary",
    "vsjo-dlja-gejmerov/xbox",
    "kollekcionnye-figurki",
    "bytovaja-tehnika/hranenie-produktov-i-napitkov",
    "sad-dacha-ogorod/tehnika-dlja-sada-i-doma/mojki-vysokogo-davlenija",
    "mebel-i-domashnij-inter-er/aksessuary-dlja-doma/shvabry-i-vedra",
    "tehnika-dlja-kuhni/prigotovlenie-napitkov",
    "krasota-i-zdorov-e/uhod-za-volosami",
    "sport-turizm-bagazh/abonementy-tehnofit",
    "suvenirnaja-produkcija",
    "santehnika-instrumenty-otoplenie/jelektroinstrument",
    "detskie-tovary/igrushki-i-igry",
    "czifrovye-produkty/po-dlja-smartfonov-i-gadzhetov",
]

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)
_PAGE_SIZE = 24
_MAX_PAGES_PER_CATEGORY = 5


class TechnodomKzSpider(scrapy.Spider):
    name = "technodom_kz"
    allowed_domains = ["technodom.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/catalog/{cat}",
                callback=self.parse_category,
                meta={"cat": cat, "page": 1},
            )

    def parse_category(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"technodom_kz: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"technodom_kz: bad JSON at {response.url}")
            return
        product_list = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialState", {})
            .get("productList", {})
        )
        items = product_list.get("items") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for it in items:
            item = self._item(it, cat, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"technodom_kz: {cat} page={page} items={n}")

        pagination = product_list.get("paginationData") or {}
        total_pages = pagination.get("totalPages") or 1
        next_page = page + 1
        if next_page <= min(total_pages, _MAX_PAGES_PER_CATEGORY):
            yield scrapy.Request(
                f"{_BASE}/catalog/{cat}?page={next_page}",
                callback=self.parse_category,
                meta={"cat": cat, "page": next_page},
            )

    def _item(self, it: dict, cat: str, scraped_at: str):
        sku = it.get("sku")
        title = (it.get("title") or "").strip()
        price = it.get("price")
        uri = it.get("uri") or ""
        if not sku or not title or not price:
            return None
        return {
            "product_id": str(sku),
            "product_name": title[:500],
            "category": (it.get("categories") or [cat])[0],
            "price": str(price),
            "currency": self.currency,
            "available": bool(it.get("is_enabled", True)),
            "url": f"{_BASE}/p/{uri}" if uri else f"{_BASE}/catalog/{cat}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
