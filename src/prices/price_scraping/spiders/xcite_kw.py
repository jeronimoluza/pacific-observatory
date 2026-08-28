"""
Spider for xcite.com — Alghanim "Xcite" electronics retailer, Kuwait.

The shard probe's lever (a same-origin Algolia search proxy at
/api/algolia/proxy) turned out to need an index name we never recovered;
this spider uses a simpler, equally-live route found while verifying that
lever: Next.js Pages Router's own data-fetching endpoint.

robots.txt -> Sitemap: https://xcite.com/sitemaps/sitemap-index.xml, which
includes sitemap-pdps.xml -> 122 shard files of real PDP URLs (curl_cffi
chrome124, no challenge). Each PDP's `/_next/data/<buildId>/product/<slug>
.json?slug=<slug>` route (buildId read at runtime from the homepage's
__NEXT_DATA__, not hardcoded -- it changes on every deploy) returns
`pageProps.meta.product` with name/brand/sku/status and a real KWD
price (`price.value`/`price.currency`), no auth, no Algolia call needed.
Confirmed live 2026-08-17: "Keychron K1 Max QMK Wireless Mechanical Gaming
Keyboard, K1M-H1-AR - Grey" -> KWD 39.900, sku from `sku` field. Rows whose
`status` is "Discontinued" (or otherwise missing `meta.product`/`price`)
have no price and are skipped -- roughly 1/3 of sampled PDPs in this catalog
are discontinued/delisted, which is normal turnover, not a scraping bug.

Enumerability: PDP sitemap shards overlap heavily (this generator is not a
clean partition -- shard 0 and shard 1 share 1002/1004 URLs), so this
spider walks a bounded number of shards and de-dupes by slug in-spider
rather than assuming disjoint pages. Sampling shards [0, 5, 10, 20, 40, 60,
80, 100, 121] already surfaced 1,246 distinct product URLs, confirming a
real multi-thousand-item catalog and not a homepage carousel.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_HOME = "https://www.xcite.com/"
_SITEMAP_INDEX = "https://www.xcite.com/sitemaps/sitemap-index.xml"
_PDP_INDEX_RE = re.compile(r"<loc>([^<]*sitemap-pdps\.xml)</loc>")
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_BUILD_ID_RE = re.compile(r'"buildId":"([^"]+)"')
# Full 122-shard walk overlaps heavily and would re-fetch the same PDPs many
# times over; this cap keeps one collect run to a bounded, still-large slice.
_MAX_SHARDS = 40


class XciteKwSpider(scrapy.Spider):
    name = "xcite_kw"
    allowed_domains = ["xcite.com"]
    currency = "KWD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_HOME, callback=self.parse_home)

    def parse_home(self, response):
        m = _BUILD_ID_RE.search(response.text)
        if not m:
            logger.warning("xcite_kw: no buildId on homepage")
            return
        build_id = m.group(1)
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"build_id": build_id},
        )

    def parse_sitemap_index(self, response):
        build_id = response.meta["build_id"]
        for loc in _PDP_INDEX_RE.findall(response.text):
            yield scrapy.Request(
                loc, callback=self.parse_pdp_index, meta={"build_id": build_id}
            )

    def parse_pdp_index(self, response):
        build_id = response.meta["build_id"]
        shard_urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info(f"xcite_kw: {len(shard_urls)} pdp shard files")
        for shard_url in shard_urls[:_MAX_SHARDS]:
            yield scrapy.Request(
                shard_url, callback=self.parse_shard, meta={"build_id": build_id}
            )

    def parse_shard(self, response):
        build_id = response.meta["build_id"]
        urls = _LOC_RE.findall(response.text)
        n = 0
        for url in urls:
            if "/ar-KW/" in url:
                continue
            slug = url.rstrip("/").rsplit(".com/", 1)[-1]
            if slug.endswith("/p"):
                slug = slug[: -len("/p")]
            if not slug:
                continue
            n += 1
            data_url = f"https://www.xcite.com/_next/data/{build_id}/product/{slug}.json?slug={slug}"
            yield scrapy.Request(
                data_url,
                callback=self.parse_product,
                meta={"slug": slug, "page_url": url},
            )
        logger.info(f"xcite_kw: {response.url} -> {n} pdp urls queued")

    def parse_product(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        product = ((data.get("pageProps") or {}).get("meta") or {}).get("product")
        if not product:
            return
        name = (product.get("name") or "").strip()
        price_block = product.get("price") or {}
        value = price_block.get("value")
        if not name or value is None:
            return

        yield {
            "product_id": str(product.get("sku") or response.meta["slug"]),
            "product_name": name[:500],
            "category": product.get("productType"),
            "price": str(value),
            "currency": price_block.get("currency") or self.currency,
            "available": str(product.get("status") or "").lower()
            not in (
                "discontinued",
                "outofstock",
            ),
            "url": response.meta["page_url"],
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
