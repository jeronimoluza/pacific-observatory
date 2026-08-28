"""
Drogasil (Brazil) - https://www.drogasil.com.br

Next.js SSR storefront behind an Akamai WAF that has TLS/JA3-fingerprinted
bare curl 403s in the past (curl_cffi impersonate=chrome124 clears it
reliably; both cleared for this session too, but the block is known to be
intermittent so impersonation stays on per the probe's recommendation).

Category pages embed a `__NEXT_DATA__` script. Two listings live inside it:
`props.pageProps.categoryListingJsonLd` (a static ~45-item bestseller
carousel that does NOT change with the page query param - a homepage-style
trap) and `props.pageProps.pageProps.results.products` (the real paginated
catalog, driven by `?p=N`, confirmed disjoint product sets between p=1 and
p=2). This spider walks the latter. Price is `priceService` (verified
against a PDP's own schema.org Offer: matches to the cent, currency BRL).

Category roots come from `props.pageProps.data.menuItems`, walked
recursively for every `url_path` in the nav tree.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.drogasil.com.br"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>')
_MAX_PAGES_PER_CATEGORY = 400  # safety cap


class DrogasilBrSpider(scrapy.Spider):
    name = "drogasil_br"
    allowed_domains = ["drogasil.com.br"]
    currency = "BRL"
    language = "pt"
    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    def _request(self, url, callback, meta=None):
        return scrapy.Request(
            url,
            callback=callback,
            meta={**(meta or {}), "impersonate": self.IMPERSONATE_PROFILE},
        )

    async def start(self):
        yield self._request(f"{_BASE}/medicamentos.html", self.parse_menu)

    def _next_data(self, text):
        m = _NEXT_DATA_RE.search(text)
        if not m:
            return None
        start = text.index(">", m.start()) + 1
        end = text.index("</script>", start)
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None

    def _collect_url_paths(self, nodes, out):
        for node in nodes:
            url_path = node.get("url_path")
            if url_path:
                out.add(url_path)
            children = node.get("children") or []
            if children:
                self._collect_url_paths(children, out)

    def parse_menu(self, response):
        data = self._next_data(response.text)
        if not data:
            logger.error("drogasil_br: no __NEXT_DATA__ on %s", response.url)
            return
        menu_items = data["props"]["pageProps"]["data"].get("menuItems", [])
        url_paths = set()
        self._collect_url_paths(menu_items, url_paths)
        logger.info("drogasil_br: %s category roots discovered", len(url_paths))
        for url_path in url_paths:
            yield self._request(
                f"{_BASE}/{url_path}?p=1",
                self.parse_category,
                meta={"url_path": url_path, "page": 1},
            )

    def parse_category(self, response):
        data = self._next_data(response.text)
        if not data:
            return
        try:
            pp = data["props"]["pageProps"]["pageProps"]
        except KeyError:
            return
        products = (pp.get("results") or {}).get("products") or []
        url_path = response.meta["url_path"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._build(p, scraped_at)
            if item:
                yield item

        if products and page < _MAX_PAGES_PER_CATEGORY:
            nxt = page + 1
            yield self._request(
                f"{_BASE}/{url_path}?p={nxt}",
                self.parse_category,
                meta={"url_path": url_path, "page": nxt},
            )

    def _build(self, p, scraped_at):
        name = p.get("name")
        price = p.get("priceService")
        sku = p.get("sku")
        if not name or price is None or not sku:
            return None
        hc = p.get("hierarchicalCategories") or {}
        category = hc.get("lvl2") or hc.get("lvl1") or hc.get("lvl0")
        url = p.get("url")
        return {
            "product_id": str(sku),
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}{url}" if url else None,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
