"""
Spider for MaxMart Online (Ghana) -- https://maxmartonline.com/.

Standard nopCommerce storefront (`meta name=generator content=nopCommerce`),
same platform as winners_mu.py, but this theme does NOT mark leaf
categories with `class="lastLevelCategory"` in the mega-menu -- that menu
is department/store-info content ("MaxMart Overview", "Meat Section")
rendered server-side but with its `category-navigation-list` populated
client-side (empty in the raw HTML; a Playwright network trace on the
homepage shows no XHR firing it, so it likely renders from an inline JS
data blob this spider does not need).

Instead this spider walks the flat `sitemap.xml` (8,131 urls total --
mixes category pages like `/yoghurts` with individual PDPs like
`/waitrose-essential-baby-cotton-wool-pleat-200g-3`, no separate
categories-only sitemap and no numeric id prefix to tell them apart from
the URL alone). Category-page responses carry `<body class=
"category-page-body">` and one-or-more `div class=product-item
data-productid=<id>` cards; PDP responses carry `<body class=
"product-details-page-body">` and simply produce zero regex matches, so
requesting every sitemap URL is safe (wasteful on PDPs, but correctness
does not depend on telling them apart up front).

Price is embedded with an explicit currency in the same span, no
guessing needed: `<span class="price actual-price">66.90 (GHS)</span>`
(confirmed live 2026-09-06, /yoghurts, productid 720 "Waitrose Essential
Baby Cotton Wool Pleat 200g" GHS 66.90 -- also confirms countries.yaml's
GHS default).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://maxmartonline.com"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(https://maxmartonline\.com/[^<]+)</loc>")
_PRODUCT_RE = re.compile(
    r"class=product-item data-productid=(?P<pid>\d+)>.*?"
    r'class=product-title><a href=(?P<url>[^ >]+)[^>]*>(?P<name>[^<]+)</a></h2>.*?'
    r'<span class="price actual-price">\s*(?P<price>[\d,]+\.\d{2})\s*\((?P<ccy>[A-Z]{3})\)\s*</span>',
    re.DOTALL,
)
PAGE_SIZE = 75
MAX_PAGES = 20  # safety cap per category
MAX_SITEMAP_URLS = 4000  # safety cap; full sitemap is 8,131 (mixed category+PDP)

# Non-catalog paths present in the sitemap that are never worth requesting.
_SKIP_PATH_RE = re.compile(
    r"/(search|blog|contactus|topic|news)(/|$|\?)", re.IGNORECASE
)


class MaxmartonlineGhSpider(scrapy.Spider):
    name = "maxmartonline_gh"
    allowed_domains = ["maxmartonline.com"]
    currency = "GHS"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if not _SKIP_PATH_RE.search(u)]
        logger.info(f"maxmartonline_gh: sitemap yielded {len(urls)} candidate urls")
        for url in urls[:MAX_SITEMAP_URLS]:
            yield scrapy.Request(
                f"{url}?pagesize={PAGE_SIZE}&pagenumber=1",
                callback=self.parse_page,
                meta={"base_url": url, "page": 1},
                dont_filter=True,
            )

    def parse_page(self, response):
        base_url = response.meta["base_url"]
        page = response.meta["page"]
        category = base_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        matches = list(_PRODUCT_RE.finditer(response.text))
        if matches:
            logger.info(f"maxmartonline_gh: {base_url} page={page} count={len(matches)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in matches:
            pid = m.group("pid")
            if pid in self._seen_ids:
                continue
            self._seen_ids.add(pid)
            yield {
                "product_id": pid,
                "product_name": m.group("name").strip(),
                "category": category,
                "price": m.group("price").replace(",", ""),
                "currency": m.group("ccy"),
                "available": True,
                "url": response.urljoin(m.group("url")),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if len(matches) >= PAGE_SIZE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{base_url}?pagesize={PAGE_SIZE}&pagenumber={nxt}",
                callback=self.parse_page,
                meta={"base_url": base_url, "page": nxt},
                dont_filter=True,
            )
