"""
Spider for Praktiker Hungary — https://praktiker.hu/.

Next.js storefront (Meilisearch-backed catalog). Every server-rendered page
embeds a `<script id="__NEXT_DATA__" type="application/json">` blob with the
full page payload — far more reliable than scraping the Tailwind-class DOM
(prices/names are duplicated many times across responsive breakpoints in the
rendered HTML). `props.pageProps.category` carries the current node's
`subcategories` list; `props.pageProps.products` carries `{products,
productCount}` for `?page=N` (1-indexed, 20/page).

The category tree is NOT flat: a node's own product listing is the UNION of
all its descendants (e.g. "Grill", 219 products, is itself the sum of its 7
child categories' counts). Scraping every node would massively
over-duplicate requests, so this only fetches products from true LEAVES
(`subcategories == []`) and recurses (without scraping) through any node
that still has children. Seeded from the homepage's embedded
`layoutProps.categories.categories` (8 top departments, each with a
`subcategories` list of second-level `/c/<id>` nodes) — deeper levels are
discovered by fetching those nodes, since the homepage payload only nests
one level.

Re-verified live 2026-08-17: homepage 200, 8 departments (Kert 5796,
Építés-felújítás 15448, Fürdőszoba 2378, Bútor 836, Műszaki-Gép-Szerszám
4500, Lakberendezés-háztartás 6713, Konyha 1022, Szabadidő 1556 — total
catalog ~38k). Leaf /kert/grill/faszenes-grill/c/630 -> 200, subcategories
[], productCount 29; real product 'Landmann Comfort Basic 53x42cm faszenes
grillkocsi takaróponyvával' id 417906, HUF 54990 (matches displayed
"54.990 Ft / darab"), status.isAvailable True.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://praktiker.hu"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
MAX_PAGES = 60


def _next_data(response):
    m = _NEXT_DATA_RE.search(response.text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


class PraktikerHuSpider(scrapy.Spider):
    name = "praktiker_hu"
    allowed_domains = ["praktiker.hu"]
    currency = "HUF"
    language = "hu"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[int] = set()

    async def start(self):
        yield scrapy.Request(f"{_BASE}/", callback=self.parse_home)

    def parse_home(self, response):
        data = _next_data(response)
        if not data:
            logger.warning("praktiker_hu: no __NEXT_DATA__ on homepage")
            return
        depts = data["props"]["pageProps"]["layoutProps"]["categories"]["categories"]
        for dept in depts:
            for node in dept.get("subcategories") or []:
                yield from self._request_node(node)

    def _request_node(self, node: dict):
        cat_id = node.get("id")
        if cat_id in self.seen_ids:
            return
        self.seen_ids.add(cat_id)
        url = urljoin(_BASE, node["link"]["url"])
        yield scrapy.Request(
            url,
            callback=self.parse_category,
            meta={"page": 1, "title": node.get("title")},
        )

    def parse_category(self, response):
        data = _next_data(response)
        if not data:
            logger.warning(f"praktiker_hu: no __NEXT_DATA__ on {response.url}")
            return
        pp = data["props"]["pageProps"]
        category = pp.get("category") or {}
        subcats = category.get("subcategories") or []

        if subcats:
            for node in subcats:
                yield from self._request_node(node)
            return

        page = response.meta["page"]
        title = response.meta.get("title") or category.get("title")
        products_block = pp.get("products") or {}
        products = products_block.get("products") or []
        product_count = products_block.get("productCount", 0)

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = (p.get("price") or {}).get("price")
            if not p.get("name") or price is None:
                continue
            yield {
                "product_id": str(p["id"]),
                "product_name": p["name"].strip()[:500],
                "category": title,
                "price": str(price),
                "currency": self.currency,
                "available": bool((p.get("status") or {}).get("isAvailable", True)),
                "url": urljoin(_BASE, p["url"]),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {response.url} page={page} products={len(products)} "
            f"total={product_count}"
        )

        if products and page * 20 < product_count and page < MAX_PAGES:
            base_url = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base_url}?page={page + 1}",
                callback=self.parse_category,
                meta={"page": page + 1, "title": title},
            )
