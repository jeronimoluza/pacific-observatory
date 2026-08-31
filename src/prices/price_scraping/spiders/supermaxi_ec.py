"""
Spider for Supermaxi (Ecuador) -- www.supermaxi.com.

Corporacion Favorita's flagship supermarket chain -- Ecuador's largest
grocery retailer. WordPress + WooCommerce storefront, but the WooCommerce
Store API (/wp-json/wc/store/v1/*) is NOT registered on this tenant
(wp-json root lists no "wc" namespace, and /wp-json/wc/store/v1/products
404s). Discovery instead uses the plain WordPress REST API: the `product`
custom post type IS exposed at /wp-json/wp/v2/products (rest_base
"products", confirmed via /wp-json/wp/v2/types), paginated the standard
WP-REST way (per_page/page, X-WP-TotalPages header). Verified live
2026-08-31: 47,269 total products across 473 pages at per_page=100.

That listing payload does NOT carry price (no price/meta field in the
response; WooCommerce's normal REST price fields are only exposed through
the Store/wc-v3 APIs, absent here). Each product's own detail page
(`link` field), however, embeds a clean JSON-LD `Product` node server-side
with `sku`, `offers.price`, `offers.priceCurrency` and
`offers.availability` -- verified live on multiple PDPs, e.g. "Queso Gouda
Rebanado MILMA 150 G" -> sku 7862120761932, USD 0.00/OutOfStock (excluded,
see below), and "Almendras Naturales Sin Cascara EL ARTESANAL 150 G" ->
USD 1.78/InStock. So discovery is Tier 1B (JSON) and price extraction is
Tier 1A (JSON-LD in the PDP HTML) -- one extra request per product, same
shape as the archived-backfill parser other Woo spiders already use, just
run live here because there is no live JSON price feed.

Category comes from the listing payload's `class_list` (`product_cat-<slug>`
entries), not from the PDP JSON-LD (which omits category).

Random 30-item sample across pages 1/50/200/500/1000 (2026-08-31): 29/30
carried a real, plausible non-zero USD price (range $0.49-$22.59); the one
$0.00 row was OutOfStock. Sample is a genuine grocery/general-merchandise
mix -- food & beverage items seen: almendras, alimento humedo para gatos,
platano fresco, limon mandarina, pimiento rojo, jamaica en flor, cafe en
capsulas, agua carbonatada, cereal, bebida en polvo -- alongside household/
non-food (USB cables, pet toys, tupperware). Rows with price "0.00" (or
missing) are dropped -- they are the OutOfStock/no-price case, not a real
observation.

Bounded: discovery walks up to MAX_LIST_PAGES catalogue pages (100
products/page) and fetches at most MAX_PRODUCTS PDPs per run -- the full
catalogue is ~47k products and would take far longer than one run;
`timeout:` is also set in the YAML. Locality: in-country ccTLD-equivalent
domain is a generic .com, but the site's own store locator lists 50+
physical Supermaxi locations across Ecuadorian cities (Guayaquil, Quito,
Cuenca, Riobamba, Salinas, Santo Domingo, Tulcan, ...) and prices are USD
(Ecuador's currency) -- proven via /catalogo/'s "local" <select>, not
domain alone.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.supermaxi.com"
_LIST_URL = _BASE + "/wp-json/wp/v2/products"
PER_PAGE = 100
MAX_LIST_PAGES = 40
MAX_PRODUCTS = 3000

_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)
_CAT_CLASS_RE = re.compile(r"^product_cat-(?!$)(.+)$")


def _category_from_class_list(class_list):
    # Each `product_cat-<slug>` entry in WordPress's class_list is a
    # directly-assigned category term, not a parent->child breadcrumb --
    # WooCommerce tags a product into several overlapping category nodes
    # (e.g. "lacteos", "quesos-lacteos", "maduros-quesos-lacteos" all on
    # one product), so joining them all produces repetitive noise. Take
    # the single most specific one (longest slug) as the category label.
    slugs = []
    for c in class_list or []:
        m = _CAT_CLASS_RE.match(c)
        if m:
            slugs.append(m.group(1).replace("-", " ").strip())
    if not slugs:
        return None
    return max(slugs, key=len)


class SupermaxiEcSpider(scrapy.Spider):
    name = "supermaxi_ec"
    allowed_domains = ["supermaxi.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._products_queued = 0

    async def start(self):
        yield scrapy.Request(
            f"{_LIST_URL}?per_page={PER_PAGE}&page=1",
            callback=self.parse_list,
            meta={"impersonate": self.IMPERSONATE_PROFILE, "page": 1},
        )

    def parse_list(self, response):
        page = response.meta["page"]
        try:
            products = response.json()
        except ValueError:
            logger.warning("supermaxi_ec: non-JSON list response at %s", response.url)
            return
        if not isinstance(products, list) or not products:
            return

        for p in products:
            if self._products_queued >= MAX_PRODUCTS:
                break
            link = p.get("link")
            if not link:
                continue
            self._products_queued += 1
            category = _category_from_class_list(p.get("class_list"))
            yield scrapy.Request(
                link,
                callback=self.parse_product,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category": category,
                    "post_id": p.get("id"),
                },
            )

        total_pages = int(response.headers.get("X-WP-TotalPages", b"0") or 0)
        if (
            self._products_queued < MAX_PRODUCTS
            and page < MAX_LIST_PAGES
            and (not total_pages or page < total_pages)
        ):
            yield scrapy.Request(
                f"{_LIST_URL}?per_page={PER_PAGE}&page={page + 1}",
                callback=self.parse_list,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "page": page + 1},
            )

    def parse_product(self, response):
        node = None
        for m in _LD_JSON_RE.finditer(response.text):
            try:
                data = json.loads(m.group(1))
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                node = data
                break
        if node is None:
            return

        name = node.get("name")
        offers = node.get("offers") or {}
        raw_price = offers.get("price")
        currency = offers.get("priceCurrency")
        if not name or raw_price is None or currency != self.currency:
            return
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return
        if price <= 0:
            return

        availability = str(offers.get("availability") or "")
        available = "outofstock" not in availability.lower()

        product_id = node.get("sku") or response.meta.get("post_id")
        if not product_id:
            return

        yield {
            "product_id": str(product_id),
            "product_name": str(name).strip()[:500],
            "category": response.meta.get("category"),
            "price": str(price),
            "currency": currency,
            "available": available,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
