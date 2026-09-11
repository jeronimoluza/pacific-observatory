"""Perfect Circle -- https://www.perfectcircle.co.bw/ (Gaborone, Botswana).

Angular SPA storefront; the SPA shell itself has no server-rendered content
and a plain-curl GET on any path (including /sitemap.xml, /robots.txt)
returns the same 200 app shell -- confirmed a Playwright network trace is
required. The real backend is a separate bespoke JSON API host,
``apiperfectcircle.kickatinalong.net`` (a white-label promo-merchandise
storefront platform; "kickatinalong.net" appears to be the SaaS vendor's
shared domain, not Perfect Circle's own infrastructure).

Flow:

1. ``GET /api/common/GetDisplayMenus`` -> flat list of 274 category nodes,
   each with ``id``, ``slug``, ``parentMenuId``. ``productTotal`` on this
   list is always 0 (not a leaf/group signal -- do not filter on it).
2. ``GET /api/common/menu/?m=<own slug>&p=<parent slug or "">&s=<offset>&t=<own id>``
   returns that node's ``product`` array (page size 10). Both root nodes
   (``p=""``) and leaf nodes return real, priced products -- the ``m``/``p``
   slug pair is what the server actually keys off; ``t`` is not tightly
   validated (a root node's ``t`` still returned real, if loosely
   categorized, products in probing). Querying every node in the flat list
   and deduping by URL is simpler and more robust than trying to infer
   which of the 274 nodes are "real" leaves.

Price is a plain BWP decimal already (``/api/Currency/Display`` confirms
``{"code":"BWP","symbol":"BWP","rate":1.0000}`` -- no minor-unit or FX
conversion needed). Many products have ``slug: null`` (only some have a
real slug); URL is built from the slug when present, else the numeric
``productId``, so every item still gets a stable, unique URL for
DuplicationPipeline dedup even though slug-less URLs are not necessarily
navigable PDPs. Company is a Botswana promotional-merchandise reseller
(Gaborone address confirmed via ``/api/common/info/``) drop-shipping from
South African wholesalers (AMROD, Barron) -- narrow apparel/promo-gift
catalog, not food.

Probed 2026-09-11 (untried_1 batch). Spider parses: API only (the emitted
``url`` values are frontend permalinks that are never fetched by this
spider; slug-less URLs are a productId-based fallback, not real pages).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_MENUS_URL = "https://apiperfectcircle.kickatinalong.net/api/common/GetDisplayMenus"
_PRODUCTS_URL = "https://apiperfectcircle.kickatinalong.net/api/common/menu/"
_PAGE_SIZE = 10
_MAX_PAGES_PER_NODE = 5  # safety cap; 50 items/node is ample for a promo-merch catalog


class PerfectcircleBwSpider(scrapy.Spider):
    name = "perfectcircle_bw"
    allowed_domains = ["apiperfectcircle.kickatinalong.net"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    HEADERS = {"Accept": "application/json"}

    async def start(self):
        yield scrapy.Request(
            _MENUS_URL, callback=self.parse_menus, headers=self.HEADERS,
            errback=self.errback,
        )

    def parse_menus(self, response):
        try:
            menus = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: non-JSON menu payload", self.name)
            return

        by_id = {m["id"]: m for m in menus if m.get("id") is not None}
        logger.info("%s: %d menu nodes", self.name, len(by_id))

        for node in by_id.values():
            slug = node.get("slug")
            if not slug:
                continue
            parent = by_id.get(node.get("parentMenuId"))
            p_slug = parent.get("slug") if parent else ""
            yield self._products_request(slug, p_slug, node["id"], 0)

    def _products_request(self, m_slug, p_slug, t_id, skip):
        url = (
            f"{_PRODUCTS_URL}?m={m_slug}&p={p_slug}&s={skip}&t={t_id}"
        )
        return scrapy.Request(
            url,
            headers=self.HEADERS,
            callback=self.parse_products,
            meta={"m_slug": m_slug, "p_slug": p_slug, "t_id": t_id, "skip": skip},
            dont_filter=True,
            errback=self.errback,
        )

    def parse_products(self, response):
        m_slug = response.meta["m_slug"]
        p_slug = response.meta["p_slug"]
        t_id = response.meta["t_id"]
        skip = response.meta["skip"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            return

        products = data.get("product") or []
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for raw in products:
            item = self._item(raw, scraped_at)
            if item:
                yield item

        if len(products) >= _PAGE_SIZE and (skip // _PAGE_SIZE) + 1 < _MAX_PAGES_PER_NODE:
            yield self._products_request(m_slug, p_slug, t_id, skip + _PAGE_SIZE)

    def _item(self, raw: dict, scraped_at: str):
        name = (raw.get("product") or "").strip()
        if not name:
            return None
        price = raw.get("price")
        try:
            amount = float(price)
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None
        pid = raw.get("productId")
        slug = raw.get("slug")
        url = (
            f"https://www.perfectcircle.co.bw/product/{slug}"
            if slug
            else f"https://www.perfectcircle.co.bw/product/id/{pid}"
        )
        cats = raw.get("categories") or []
        category = " | ".join(
            c.get("category") for c in cats if c.get("category")
        ) or None
        return {
            "product_id": str(pid) if pid else None,
            "product_name": name,
            "category": category,
            "price": f"{amount:.2f}",
            "currency": self.currency,
            "available": bool(raw.get("active", True)),
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
