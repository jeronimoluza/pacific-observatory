"""
Migros (Turkiye) -- https://www.migros.com.tr/.

Angular SPA storefront. Category pages ship no products in the raw HTML
(hydrated client-side), but the client's own call is a wide-open JSON^H^H
custom-XML API with no auth, no cookies, no store-selection required:

    GET /rest/search/screens/<category-pretty-name>?sayfa=<page>
    -> <AppResponse><data><searchInfo><pageCount>N</pageCount>
       <hitCount>M</hitCount></searchInfo><storeProductInfos>
       <storeProductInfos>...</storeProductInfos>...</storeProductInfos>
       </data></AppResponse>

Discovered via a Playwright network trace on a category page -- the plain
`/rest/products/search` endpoint the brief suggested returns hitCount=0
without extra params; this is the endpoint the SPA actually calls.
`sayfa` (Turkish for "page") is a real, 1-based page counter -- confirmed
distinct SKU sets across pages 1-3 of meyve-sebze-c-2. Body is XML despite
a Content-Type of `application/xhtml+xml`; parsed with lxml.etree.

Prices come back in kurus (minor units) as `shownPrice` (post-discount,
what the customer pays) vs `regularPrice` (pre-discount list price) --
divide `shownPrice` by 100. Verified against a rendered PDP: potato
(Patates Yeni Mahsul Kg) priced 41.95 TRY/kg on 2026-08-31, plausible for
Turkiye's high-inflation retail environment.

Category list is the ~20 non-special top-level categories from
`/rest/categories/top-level` (specialCategory=true entries are seasonal
promo tabs, not real catalog nodes) -- each top-level slug's own
`/rest/search/screens/<slug>` endpoint already returns the full paginated
catalog for that department (no need to descend into subcategories).
"""

import logging
from datetime import datetime, timezone

import scrapy
from lxml import etree

logger = logging.getLogger(__name__)

BASE_URL = "https://www.migros.com.tr"

# Non-special top-level category slugs from /rest/categories/top-level,
# spanning food (fruit/veg, meat, dairy, groceries, drinks, snacks,
# bakery, ready meals, frozen) and non-food (cleaning, personal care,
# baby, home, pet, electronics) departments.
CATEGORY_SLUGS = [
    "meyve-sebze-c-2",
    "et-tavuk-balik-c-3",
    "sut-kahvaltilik-c-4",
    "temel-gida-c-5",
    "icecek-c-6",
    "atistirmalik-c-113fb",
    "dondurma-c-41b",
    "firin-pastane-c-7e",
    "hazir-yemek-meze-c-7d",
    "dondurulmus-gida-c-7c",
    "deterjan-temizlik-c-7",
    "kisisel-bakim-kozmetik-saglik-c-8",
    "kagit-islak-mendil-c-8d",
    "bebek-c-9",
    "ev-yasam-c-a",
    "evcil-hayvan-c-a0",
]


class MigrosTrSpider(scrapy.Spider):
    name = "migros_tr"
    allowed_domains = ["migros.com.tr"]
    currency = "TRY"
    language = "tr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in CATEGORY_SLUGS:
            yield self._api_request(slug, 1)

    def _api_request(self, slug, page):
        return scrapy.Request(
            f"{BASE_URL}/rest/search/screens/{slug}?sayfa={page}",
            callback=self.parse_api,
            errback=self.errback,
            meta={"slug": slug, "page": page},
            dont_filter=True,
        )

    def parse_api(self, response):
        slug, page = response.meta["slug"], response.meta["page"]
        try:
            root = etree.fromstring(response.body)
        except etree.XMLSyntaxError:
            logger.warning(f"{self.name}: non-XML from {response.url}")
            return

        items = root.findall(".//storeProductInfos[sku]")
        for item in items:
            name = (item.findtext("name") or "").strip()
            shown_price = item.findtext("shownPrice")
            pretty_name = item.findtext("prettyName")
            product_id = item.findtext("id") or item.findtext("sku")
            if not name or not shown_price or not pretty_name:
                continue
            try:
                price = float(shown_price) / 100
            except ValueError:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": item.findtext("category/name"),
                "price": str(price),
                "currency": self.currency,
                "available": (item.findtext("status") == "IN_SALE"),
                "url": f"{BASE_URL}/{pretty_name}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        search_info = root.find(".//searchInfo")
        page_count = (
            int(search_info.findtext("pageCount") or 0)
            if search_info is not None
            else 0
        )
        hit_count = (
            search_info.findtext("hitCount") if search_info is not None else None
        )
        logger.info(
            f"{self.name}: slug={slug} page={page} got={len(items)} "
            f"pageCount={page_count} hitCount={hit_count}"
        )

        if items and page < page_count:
            yield self._api_request(slug, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
