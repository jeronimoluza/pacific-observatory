"""
Shared base class for Axfood-group storefronts (SAP Commerce Cloud).

Willys and Hemkop are both Axfood-group Swedish grocery chains and share
the identical "axfood/rest/v1" backend confirmed live 2026-09-10:

    GET https://<domain>/axfood/rest/v1/c/<category-path>?page=<n>

returns {"results": [...], "pagination": {"currentPage", "numberOfPages",
"totalNumberOfResults", ...}, "categoryBreadcrumbs": {...}, ...}. The
server ignores any pageSize query param and always returns 10 items per
page; page 0 and page 1 of the same category return disjoint product
`code` sets (confirmed on both tenants).

Category paths are discovered from the tenant's own sitemap.xml ->
"Category-*.xml" child sitemap, which lists every /sortiment/<path> URL
on the site (a few hundred leaf + intermediate categories). Both tenants'
top-level sitemap.xml has a live bug: every <loc> is the domain
concatenated with itself twice (e.g.
"https://www.willys.sehttps://www.willys.se/medias/..."). _clean_loc()
strips the duplicate; without it every sitemap request 404s.

`priceValue` in each result item is already a decimal float in the
tenant's currency (no minor-unit division needed, unlike WooCommerce).

Subclasses set: name, allowed_domains, currency, language, DOMAIN.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
MAX_CATEGORIES = 600  # safety cap; sitemap holds a few hundred category paths
MAX_PAGES_PER_CATEGORY = 40  # safety cap; pagination.numberOfPages is authoritative below that


class AxfoodBaseSpider(scrapy.Spider):
    name = None
    DOMAIN: str = ""  # e.g. "www.willys.se"
    currency = "SEK"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    @staticmethod
    def _clean_loc(loc: str) -> str:
        # sitemapindex/urlset <loc> values are the domain concatenated with
        # itself -- keep only the last "https://" onward.
        if loc.count("https://") > 1:
            loc = "https://" + loc.split("https://", 2)[-1]
        return loc

    async def start(self):
        yield scrapy.Request(
            f"https://{self.DOMAIN}/sitemap.xml",
            callback=self.parse_sitemap_index,
        )

    def parse_sitemap_index(self, response):
        locs = [self._clean_loc(u) for u in _LOC_RE.findall(response.text)]
        cat_sitemaps = [u for u in locs if "/medias/Category-" in u]
        logger.info(f"{self.name}: {len(cat_sitemaps)} category sitemap(s)")
        for u in cat_sitemaps:
            yield scrapy.Request(u, callback=self.parse_category_sitemap)

    def parse_category_sitemap(self, response):
        locs = [self._clean_loc(u) for u in _LOC_RE.findall(response.text)]
        paths = []
        seen = set()
        for u in locs:
            m = re.search(r"\.se/sortiment/([^\s<]+)", u)
            if not m:
                continue
            path = m.group(1).strip("/")
            if not path or "//" in path or path in seen:
                continue
            seen.add(path)
            paths.append(path)
        logger.info(f"{self.name}: sitemap yields {len(paths)} category paths")
        for path in paths[:MAX_CATEGORIES]:
            yield self._category_request(path, 0)

    def _category_request(self, path, page):
        url = f"https://{self.DOMAIN}/axfood/rest/v1/c/{path}?page={page}"
        return scrapy.Request(
            url,
            callback=self.parse_category,
            meta={"path": path, "page": page},
            errback=self._on_error,
        )

    def _on_error(self, failure):
        logger.debug(f"{self.name}: request failed {failure.request.url}")

    def parse_category(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            return
        results = data.get("results") or []
        path = response.meta["path"]
        page = response.meta["page"]
        pagination = data.get("pagination") or {}
        breadcrumb = data.get("categoryBreadcrumbs") or {}
        category_name = breadcrumb.get("name") or path
        logger.info(f"{self.name}: path={path} page={page} items={len(results)}")
        for item in results:
            price = item.get("priceValue")
            if not price:
                continue
            code = item.get("code")
            yield {
                "product_id": code,
                "product_name": item.get("name"),
                "price": price,
                "currency": self.currency,
                "category": category_name,
                # /produkt/<code> is a real per-product PDP route (confirmed
                # 200 on both willys.se and hemkop.se). A category-listing
                # URL shared by every product on the page would collide in
                # pipelines.py's url-dedup (it hashes item["url"] and drops
                # every item after the first on a shared URL).
                "url": f"https://{self.DOMAIN}/produkt/{code}" if code else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        number_of_pages = pagination.get("numberOfPages") or 1
        if results and page + 1 < number_of_pages and page + 1 < MAX_PAGES_PER_CATEGORY:
            yield self._category_request(path, page + 1)
