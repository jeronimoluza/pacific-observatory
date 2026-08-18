"""
Spider for Liverpool Mexico -- www.liverpool.com.mx.

Next.js App Router storefront streaming React Server Components (flight
data in <script> chunks, no single __NEXT_DATA__ blob) behind Akamai.
robots.txt explicitly Allows ClaudeBot/Claude-SearchBot/Claude-User.

The site's own /sitemap/sitemap.xml lists per-department sitemap files
(electronica.xml, hogar.xml, 1pdp.xml, ...) but every one of those 404s
through the Next.js app (checked live 2026-08-17: the index itself is
served straight off AkamaiNetStorage, but every category/pdp sitemap file
it points to returns a Next.js 404 page instead of XML -- the site appears
to be mid-migration, per the `gcp-migrated=true` cookie). So this spider
does not use the sitemap.

Instead it walks real category listing pages discovered from the homepage
nav (`/tienda/<slug>/<catId>`), which paginate via a path segment --
`/tienda/<slug>/<catId>/page-N` -- NOT `?page=N` (confirmed: `?page=2`
returns page 1 again, 51/53 id overlap; `/page-2` returns 56 ids with only
1/52 overlap vs `/page-1`). Category pages render each card server-side
with a `data-testid="<productId>-card-card-link"` anchor (name in the
following `<img alt="...">`, price in a
`data-testid="<productId>-price"` block split into whole/cents spans).
Some categories (cocina, electrodomesticos-de-cocina) return 0 cards on
this plain path and need a `?showPLP` query the homepage links carry --
left out of scope here, use the 5 categories below which are confirmed
live.

Re-verified live 2026-08-17: celulares/cat5150024, laptops/catst10075558,
pantalones/cat3980003, blusas/catst4003088 all show a materially different
id set between /page-1 and /page-2 (0-1 id overlap out of 52-56).
consolas-nintendo/catst16854843 has only one real page (page-2 404s) --
self-limits via the `if n == 0` check below.
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.liverpool.com.mx"
_CATEGORIES = [
    ("celulares", "tienda/celulares/cat5150024"),
    ("laptops", "tienda/laptops/catst10075558"),
    ("pantalones", "tienda/pantalones/cat3980003"),
    ("blusas", "tienda/blusas/catst4003088"),
    ("consolas-nintendo", "tienda/consolas-nintendo/catst16854843"),
]
MAX_PAGES = 20

_ANCHOR_RE = re.compile(r'data-testid="(\d+)-card-card-link"[^>]*href="([^"]+)"')
_ALT_RE = re.compile(r'alt="([^"]+)"')
_DISCOUNTED_RE = re.compile(
    r'data-testid="discounted"[^>]*>\s*<span>\$<!-- -->([\d,]+)</span>'
    r"<span[^>]*><span[^>]*>\.</span>(\d+)</span>"
)
_ORIGINAL_RE = re.compile(
    r'data-testid="original"[^>]*>\s*(?:<span[^>]*>)?\$<!-- -->([\d,]+)</span>'
)


def _parse_price(block):
    m = _DISCOUNTED_RE.search(block)
    if m:
        return m.group(1).replace(",", "") + "." + m.group(2)
    m = _ORIGINAL_RE.search(block)
    if m:
        return m.group(1).replace(",", "")
    return None


class LiverpoolMxSpider(scrapy.Spider):
    name = "liverpool_mx"
    allowed_domains = ["liverpool.com.mx"]
    currency = "MXN"
    language = "es"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        for label, path in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{path}/page-1",
                callback=self.parse_listing,
                meta={
                    "label": label,
                    "page": 1,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )

    def parse_listing(self, response):
        label = response.meta["label"]
        page = response.meta["page"]
        text = response.text

        matches = list(_ANCHOR_RE.finditer(text))
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i, m in enumerate(matches):
            product_id = m.group(1)
            if product_id in self.seen_ids:
                continue
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else start + 4000
            block = text[start:end]
            alt_m = _ALT_RE.search(block)
            name = html.unescape(alt_m.group(1)).strip() if alt_m else None
            if not name or name == "Imagen de producto":
                continue
            price = _parse_price(block)
            if not price:
                continue
            self.seen_ids.add(product_id)
            n += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": label,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, m.group(2)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("liverpool_mx: %s page=%d rows=%d", label, page, n)

        if len(matches) > 0 and page < MAX_PAGES:
            next_path = (
                f"tienda/{response.url.split('/tienda/', 1)[1].rsplit('/page-', 1)[0]}"
            )
            yield scrapy.Request(
                f"{_BASE}/{next_path}/page-{page + 1}",
                callback=self.parse_listing,
                meta={
                    "label": label,
                    "page": page + 1,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )
