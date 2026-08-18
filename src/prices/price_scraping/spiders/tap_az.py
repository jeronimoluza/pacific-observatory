"""tap.az — Azerbaijan classifieds marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: category listing pages
(``https://tap.az/elanlar/<slug>``) are Next.js SSR and embed every ad shown
on the page as a clean ``Ad`` object inside
``<script id="__NEXT_DATA__">``'s ``props.pageProps.apolloState`` — ``id``,
``title``, ``price`` (already a bare number, no locale parsing needed),
``path`` (relative ad URL), ``legacyResourceId``. All 28 sampled ads on the
Elektronika category page rendered with the ``₼`` (manat) glyph and no
alternate-currency ads were seen, so currency is hardcoded AZN rather than
parsed per-row.

IMPORTANT — ``?page=<N>`` does NOT paginate here, despite initially looking
like it did: the SSR payload's ``adSearch`` connection (the real organic
listing, under ``ROOT_QUERY``) always ships the identical first cursor batch
(``pageInfo.endCursor`` is the same ``"MjQ"`` on every page; verified
page 1/2/20 of the same category share 23-24 of 28 ads). Real pagination is
client-side GraphQL with a cursor, not reachable via a plain URL. So instead
of walking fake pages, this spider walks real distinct category URLs: the 9
top-level categories (from ``rootCategories`` on the homepage, excluding
``is-elanlari`` job postings) plus every ``<category>/<subcategory>`` leaf
path discovered by sampling the first few shards of the site's own ad
sitemap (``sitemap.xml`` -> per-shard ``<loc>`` URLs of the form
``elanlar/<cat>/<subcat>/<id>``; 3 shards of 25k ad URLs each already
saturates the ~110-leaf taxonomy, confirmed by diminishing new-category
yield across shards 1-3). Each category/subcategory URL is requested once
(no page param) — every request returns a genuinely different SSR batch.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_CATEGORY_URL_RE = re.compile(r"^https://tap\.az/elanlar/([a-z-]+)/([a-z-]+)/\d+$")

_SITEMAP_INDEX = "https://tap.az/sitemap.xml"
_MAX_SITEMAP_SHARDS = 3

_TOP_CATEGORIES = (
    "ev-ve-bag-ucun",
    "neqliyyat",
    "elektronika",
    "dasinmaz-emlak",
    "xidmetler",
    "sexsi-esyalar",
    "hobbi-ve-asude",
    "usaqlar-ucun",
    "heyvanlar",
)


class TapAzSpider(scrapy.Spider):
    name = "tap_az"
    allowed_domains = ["tap.az", "tap.azstatic.com"]
    currency = "AZN"
    language = "az"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()
        self.requested_paths: set[str] = set()

    async def start(self):
        for slug in _TOP_CATEGORIES:
            self.requested_paths.add(slug)
            yield scrapy.Request(
                f"https://tap.az/elanlar/{slug}",
                callback=self.parse_page,
                meta={"slug": slug},
            )
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        shard_urls = _LOC_RE.findall(response.text)[:_MAX_SITEMAP_SHARDS]
        logger.info(
            "tap_az: sampling %d ad-sitemap shards for subcategories", len(shard_urls)
        )
        for url in shard_urls:
            yield scrapy.Request(url, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        subcats = set()
        for loc in _LOC_RE.findall(response.text):
            m = _CATEGORY_URL_RE.match(loc)
            if m:
                subcats.add(f"{m.group(1)}/{m.group(2)}")

        new_paths = sorted(subcats - self.requested_paths)
        logger.info(
            "tap_az: %s -> %d subcategories seen, %d new",
            response.url,
            len(subcats),
            len(new_paths),
        )
        for path in new_paths:
            self.requested_paths.add(path)
            yield scrapy.Request(
                f"https://tap.az/elanlar/{path}",
                callback=self.parse_page,
                meta={"slug": path},
            )

    def parse_page(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("tap_az: no __NEXT_DATA__ on %s", response.url)
            return

        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning("tap_az: unparseable __NEXT_DATA__ on %s", response.url)
            return

        page_props = data.get("props", {}).get("pageProps", {})
        apollo = page_props.get("apolloState", {})
        current_category = page_props.get("currentCategory") or {}
        category = current_category.get("name")

        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for key, node in apollo.items():
            if not key.startswith("Ad:") or not isinstance(node, dict):
                continue
            item = self._parse_ad(node, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        logger.info(
            "slug=%s items=%d cumulative=%d",
            response.meta["slug"],
            emitted,
            len(self.seen_ids),
        )

    def _parse_ad(
        self, node: dict, category: str | None, scraped_at: str
    ) -> dict | None:
        ad_id = node.get("legacyResourceId")
        if ad_id is None:
            return None
        ad_id = str(ad_id)
        if ad_id in self.seen_ids:
            return None

        title = node.get("title")
        price = node.get("price")
        path = node.get("path")
        if not title or price is None or not path:
            return None

        self.seen_ids.add(ad_id)
        return {
            "product_id": ad_id,
            "product_name": str(title)[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": node.get("status", "APPROVED") == "APPROVED",
            "url": f"https://tap.az{path}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
