"""
Shared base class for VTEX-platform spiders (Cencosud, Walmart Centroamerica,
and independent VTEX tenants across LAC).

VTEX's catalog_system product-search endpoint caps out around `_from=2500`
overall, so a whole-catalog crawl must partition by category rather than
walk the flat endpoint. We fetch `/api/catalog_system/pub/category/tree/3`,
flatten it to its leaf-most nodes (nodes whose `children` list is empty --
either a true leaf or a depth-3 cutoff node), and page each leaf's full
root-to-leaf id path (`fq=C:/<id>/<id>/.../`) in windows of 50
(`_to - _from` must be <= 49; larger windows return HTTP 400). Querying a
category by its full id path returns products from that category AND all
its descendants (verified live via the `resources: from-to/total` response
header on a parent vs. child category), so leaf-only crawling is both
disjoint and complete without re-walking every tree level.

Subclasses set: name, allowed_domains, HOST, currency, language.
Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
MAX_PAGES_PER_CATEGORY = 60  # safety cap: 60 * 50 = 3000 items/leaf category


class VtexBaseSpider(scrapy.Spider):
    name = None
    HOST: str = ""

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        self.seen_skus = set()
        yield scrapy.Request(
            f"https://{self.HOST}/api/catalog_system/pub/category/tree/3",
            callback=self.parse_tree,
        )

    def parse_tree(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON category tree at {response.url}")
            return
        leaves = []
        self._collect_leaves(tree, [], leaves)
        logger.info(f"{self.name}: {len(leaves)} leaf categories")
        for path, cat_name in leaves:
            yield self._page_request(path, cat_name, 0)

    def _collect_leaves(self, nodes, path, leaves):
        for node in nodes or []:
            node_path = path + [str(node.get("id"))]
            children = node.get("children") or []
            if children:
                self._collect_leaves(children, node_path, leaves)
            else:
                leaves.append((node_path, node.get("name")))

    def _page_request(self, path, cat_name, from_):
        to_ = from_ + PAGE_SIZE - 1
        fq = "/".join(path)
        url = (
            f"https://{self.HOST}/api/catalog_system/pub/products/search"
            f"?fq=C:/{fq}/&_from={from_}&_to={to_}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"path": path, "cat_name": cat_name, "from_": from_},
            dont_filter=True,
        )

    def parse_page(self, response):
        if response.status not in (200, 206):
            return
        try:
            products = response.json()
        except ValueError:
            return
        if not isinstance(products, list) or not products:
            return
        path = response.meta["path"]
        cat_name = response.meta["cat_name"]
        from_ = response.meta["from_"]
        for p in products:
            for item in self._items(p, cat_name):
                yield item
        page_num = from_ // PAGE_SIZE
        if len(products) >= PAGE_SIZE and page_num + 1 < MAX_PAGES_PER_CATEGORY:
            yield self._page_request(path, cat_name, from_ + PAGE_SIZE)

    def _items(self, p: dict, cat_name):
        categories = p.get("categories") or []
        category = (
            categories[0].strip("/").replace("/", " > ") if categories else cat_name
        )
        link_text = p.get("linkText")
        url = (
            f"https://{self.HOST}/{link_text}/p" if link_text else (p.get("link") or "")
        )
        product_name = str(p.get("productName") or "").strip()[:500]
        for it in p.get("items") or []:
            sku_id = it.get("itemId")
            if not sku_id or sku_id in self.seen_skus:
                continue
            sellers = it.get("sellers") or []
            if not sellers:
                continue
            seller = next((s for s in sellers if s.get("sellerDefault")), sellers[0])
            offer = seller.get("commertialOffer") or {}
            price = offer.get("Price")
            available_qty = offer.get("AvailableQuantity")
            if available_qty == 0 and not price:
                continue
            if price is None:
                continue
            self.seen_skus.add(sku_id)
            yield {
                "product_id": str(sku_id),
                "product_name": product_name,
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(available_qty) if available_qty is not None else True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
