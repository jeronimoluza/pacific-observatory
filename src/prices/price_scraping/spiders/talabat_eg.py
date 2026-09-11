"""
Spider for Talabat Egypt groceries — https://www.talabat.com/egypt/groceries.

Talabat (Delivery Hero) is a food-delivery AGGREGATOR, not a retailer -- see
GLOSSARY.md on `channel: aggregator` being split into `marketplace` (third-
party sellers) / `real-estate` / null. Its "groceries" vertical is exactly
the marketplace case: dozens of independently-run grocery stores, mini-
markets, pharmacies and supermarket chains (e.g. BIM's Egyptian branches)
each keep their own SKU-level catalog and their own prices, sold through
Talabat's storefront. Channel is set to `marketplace` accordingly, not
`supermarket` -- no single retailer identity applies to this source.

Rejected as NOT part of the price panel: vendors whose own `cuisineString`
contains "Charity" (Egyptian Food Bank, hospital/foundation donation-drive
listings -- e.g. "57357 Hospital", "Magdi Yacoub Heart Foundation" -- all
appear on the public groceries-area listing pages alongside real retailers).
These are aid distribution, not retail price observations, and were excluded
at crawl time rather than relying on a downstream zero-price filter.

The restaurant side of Talabat (COICOP 11.1 catering, a completely separate
`restaurants-N.xml.gz` sitemap family) is explicitly OUT of scope for this
source -- this spider only walks the `groceries_areas` sitemap.

TLS profile: repo-pinned chrome120 was reported 403 in the batch brief but
re-probed live 2026-09-10 chrome120 actually 200s on /egypt (inconsistent --
possibly A/B'd at the edge); chrome124/chrome119/chrome131 403 reliably;
chrome133a 200s reliably on every host path tried (homepage, sitemap, area,
vendor, item pages). Pinned via the same 3-part IMPERSONATE_PROFILE override
used for rewe_de/libdelivery_lr (disable RandomBrowserMiddleware + matching
UA + IMPERSONATE_PROFILE) since a mixed result is not a profile to trust.

Crawl shape (3 hops, all server-rendered Next.js `__NEXT_DATA__` JSON, no
client-side API calls needed):
  1. sitemap egypt/en/groceries_areas.xml.gz -> ~1,910 area pages
     (/egypt/groceries/<areaId>/<slug>), each paginated (?page=N).
  2. Each area page's `pageProps.vendors[]` lists grocery vendors serving
     that area (branchId/branchSlug) -- deduplicated globally by branchId
     since the same physical store serves many nearby areas under the same
     id (confirmed: "Disha Market" branchId 707053 recurs across areas).
     Only visited once per branchId regardless of how many areas surface it.
  3. Each vendor page (/egypt/grocery/<branchId>/<slug>?aid=<areaId>) lists
     its own category/subCategory tree in `pageProps.initialState.categories`
     with a per-subcategory item `count`; each subcategory page
     (.../<catSlug>/<subCatSlug>?aid=<areaId>) embeds the priced item list
     directly in `pageProps.initialState.itemsData.items[]`
     (title/price/originalPrice/sku), paginated via `&page=N` up to
     `itemsData.pageCount`.

Enumerability confirmed live 2026-09-10 on vendor 707053 (Disha Market),
category snacks-chocolate/biscuits (148 items, pageCount=7): page 1 vs page
2 are a disjoint 20/20 item-id set, zero overlap. Real EGP prices throughout
(e.g. "Galaxy Flutes 4 Fingers Chocolate Wafer Rolls, 45g" EGP 22.80, sku
6221134002638 -- a 622-prefixed EAN, Egypt's GS1 country code, confirming
these are genuine Egyptian retail SKUs and not a copied foreign catalog).

No explicit currency field in the item JSON; EGP is inferred from the
/egypt/ country scope (same convention as every other spider in this repo
that infers currency from the country tree rather than a per-row field).
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.talabat.com/sitemap/egypt/en/groceries_areas.xml.gz"
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_AREA_URL_RE = re.compile(r"/egypt/groceries/(\d+)/")
_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__" type="application/json">(\{.*?\})</script>', re.S
)

MAX_AREA_PAGES = 3  # safety cap on per-area vendor-list pagination
MAX_ITEM_PAGES = 15  # safety cap on per-subcategory item pagination


def _next_data(response):
    m = _NEXT_DATA_RE.search(response.text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


class TalabatEgSpider(scrapy.Spider):
    name = "talabat_eg"
    allowed_domains = ["talabat.com", "www.talabat.com"]
    currency = "EGP"
    language = "en"

    IMPERSONATE_PROFILE = "chrome133a"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_vendor_ids: set[int] = set()

    def _meta(self, extra: dict | None = None) -> dict:
        meta = dict(extra or {})
        meta["impersonate"] = self.IMPERSONATE_PROFILE
        return meta

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap, meta=self._meta())

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        area_urls = [u for u in locs if _AREA_URL_RE.search(u)]
        logger.info(f"talabat_eg: sitemap urls={len(locs)} areas={len(area_urls)}")
        for url in area_urls:
            yield scrapy.Request(
                url, callback=self.parse_area, meta=self._meta({"area_page": 1})
            )

    def parse_area(self, response):
        area_m = _AREA_URL_RE.search(response.url)
        area_id = area_m.group(1) if area_m else None
        data = _next_data(response)
        if not data:
            return
        vendors = (data.get("props") or {}).get("pageProps", {}).get("vendors") or []
        new_count = 0
        for v in vendors:
            branch_id = v.get("branchId")
            cuisine = (v.get("cuisineString") or "").lower()
            if not branch_id or "charity" in cuisine:
                continue
            if branch_id in self.seen_vendor_ids:
                continue
            self.seen_vendor_ids.add(branch_id)
            new_count += 1
            slug = v.get("branchSlug") or v.get("restaurantSlug")
            if not slug:
                continue
            vendor_url = f"https://www.talabat.com/egypt/grocery/{branch_id}/{slug}?aid={area_id}"
            yield scrapy.Request(vendor_url, callback=self.parse_vendor, meta=self._meta())

        page = response.meta.get("area_page", 1)
        if vendors and page < MAX_AREA_PAGES:
            base = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base}?page={page + 1}",
                callback=self.parse_area,
                meta=self._meta({"area_page": page + 1}),
            )
        logger.info(
            f"talabat_eg: area={response.url} vendors={len(vendors)} new={new_count}"
        )

    def parse_vendor(self, response):
        data = _next_data(response)
        if not data:
            return
        initial = (data.get("props") or {}).get("pageProps", {}).get("initialState") or {}
        categories = initial.get("categories") or []
        qs = parse_qs(urlparse(response.url).query)
        aid = qs.get("aid", [""])[0]
        vendor_path = response.url.split("?")[0]
        for cat in categories:
            for sub in cat.get("subCategories") or []:
                sub_url = f"{vendor_path}/{cat.get('slug')}/{sub.get('slug')}?aid={aid}"
                yield scrapy.Request(
                    sub_url,
                    callback=self.parse_items,
                    meta=self._meta({"item_page": 1, "base_url": sub_url}),
                )

    def parse_items(self, response):
        data = _next_data(response)
        if not data:
            return
        items_data = (
            (data.get("props") or {})
            .get("pageProps", {})
            .get("initialState", {})
            .get("itemsData")
            or {}
        )
        items = items_data.get("items") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            price = it.get("price")
            name = (it.get("title") or "").strip()
            item_id = it.get("sku") or it.get("id")
            if not name or not price or price <= 0 or not item_id:
                continue
            # DuplicationPipeline dedupes on the item's own "url" field, and
            # this page's response.url is shared by every product on it --
            # a bare `response.url` here would make the pipeline treat every
            # item after the first on a subcategory page as a duplicate of
            # it and silently drop it. Append the item id as a query param
            # (harmless on a real fetch -- the site ignores unknown params
            # and still serves the same subcategory listing) so each product
            # gets its own hash.
            yield {
                "product_id": item_id,
                "product_name": name[:500],
                "price": str(price),
                "currency": self.currency,
                "category": None,
                "url": f"{response.url}&talabatItemId={item_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        page = response.meta.get("item_page", 1)
        page_count = items_data.get("pageCount") or 1
        if items and page < page_count and page < MAX_ITEM_PAGES:
            base_url = response.meta["base_url"]
            yield scrapy.Request(
                f"{base_url}&page={page + 1}",
                callback=self.parse_items,
                meta=self._meta({"item_page": page + 1, "base_url": base_url}),
            )
