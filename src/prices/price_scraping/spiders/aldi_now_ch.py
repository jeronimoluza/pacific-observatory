"""
Spider for ALDI now (Switzerland) — https://www.aldi-now.ch/.

Server-rendered, custom storefront (no Next.js/Nuxt marker). Category
listing pages (e.g. /de/genussmittel/tabakwaren) render ~20 product cards
per page as `<product-item>` custom elements. Each card also carries a
Google-Analytics `onclick="return GA_onAddToCart([{...}])"` blob with a
clean, structured JSON object (item_name, item_id, price, item_brand,
item_category/2/3) -- easier and more reliable to parse than the visual
markup, and confirmed to match the rendered price.

Category discovery: /sitemap.xml lists both category and product URLs
(no separate sitemap-index). This spider fetches it live each run and
walks only LEAF categories (paths with no child path also present in the
sitemap -- same "keep only leaves" approach as spar_si) to avoid
re-fetching the same products once per ancestor category. Verified live
2026-09-06: sitemap.xml has 1421 category paths (1344 leaves) and 7955
distinct product paths.

Verified live 2026-09-06: GET /de/genussmittel -> 20
`GA_onAddToCart` blobs, e.g. item_id 720990 "THE KING Blue Zigaretten"
CHF 5.99, item_category3 "Tabakwaren". GET
/de/milsani-high-protein-shots-erdbeere/662130002 (a PDP) independently
confirms price 3.69 rendered in `volume-price__price` -- category-page
price and PDP price agree.

GOTCHA (from candidate brief): checkout adds a 2.5% picking fee plus CHF
1.50 transport-material fee on top of the listed price -- this spider
records the listed shelf price, not the checkout total.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.aldi-now.ch"
_GA_RE = re.compile(r"GA_onAddToCart\(\[(\{.*?\})\]\)")


class AldiNowChSpider(scrapy.Spider):
    name = "aldi_now_ch"
    allowed_domains = ["aldi-now.ch"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/sitemap.xml", callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = re.findall(r"<loc>([^<]+)</loc>", response.text)
        cat_paths = []
        for loc in locs:
            path = urlparse(html.unescape(loc)).path
            segs = [s for s in path.split("/") if s]
            if len(segs) < 2 or segs[-1].isdigit():
                continue  # root or a product URL
            cat_paths.append(path)

        path_set = set(cat_paths)
        leaves = [
            p
            for p in cat_paths
            if not any(other != p and other.startswith(p + "/") for other in path_set)
        ]
        logger.info(f"aldi_now_ch: {len(cat_paths)} category paths, {len(leaves)} leaves")
        for path in leaves:
            yield scrapy.Request(
                _BASE + path, callback=self.parse_category, meta={"path": path}
            )

    def parse_category(self, response):
        path = response.meta["path"]
        blobs = _GA_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for blob in blobs:
            try:
                obj = json.loads(html.unescape(blob))
            except json.JSONDecodeError:
                continue
            price = obj.get("price")
            item_id = obj.get("item_id")
            if not price or not item_id:
                continue
            count += 1
            category = obj.get("item_category3") or obj.get("item_category2") or None
            yield {
                "product_id": str(item_id),
                "product_name": str(obj.get("item_name", "")).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                # The GA blob has no PDP slug, only item_id -- use the
                # leaf-category path + item_id fragment as a stable,
                # unique-per-product URL (DuplicationPipeline dedups on
                # this field, and item_id is unique catalogue-wide).
                "url": f"{_BASE}{path}#{item_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"aldi_now_ch: {path} items={count}")
