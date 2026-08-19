"""
Shared base classes for Magento 2 storefronts.

Two independent surfaces are exposed by this base, matched to what the
onboarding probe found live for each site:

- ``MagentoGraphQLBaseSpider`` — POSTs to a GraphQL endpoint (either the
  storefront's own ``/graphql`` or a separate ``mcprod.<domain>/graphql``
  backend some Nuxt-fronted installs use) and walks ``categoryList`` ->
  ``products(filter: {category_id: {eq: ...}} pageSize currentPage)``.
- ``MagentoSSRBaseSpider`` — crawls server-rendered category/listing HTML
  pages where the GraphQL/REST surfaces are closed (401/404) but Luma-theme
  product-item cards carry ``product-item-link`` name anchors and
  ``data-price-amount`` price attributes directly in the markup.

Subclasses set a handful of class attributes; pagination, item-dict shaping
and politeness settings are inherited.

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

from ..archived import normalize_price, row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_POLITE_SETTINGS = {
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

_CATEGORY_LIST_QUERY = """
{ categoryList(filters: {ids: {eq: "%s"}}) { id children { id name product_count } } }
"""

_PRODUCTS_QUERY = """
{ products(filter: {category_id: {eq: "%s"}}, pageSize: %d, currentPage: %d) {
    total_count
    items {
      sku
      name
      url_key
      price_range { minimum_price { final_price { value currency } } }
    }
  }
}
"""


class MagentoGraphQLBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language,
    # GRAPHQL_URL, BASE_URL, ROOT_CATEGORY_ID.
    name = None
    GRAPHQL_URL: str = ""
    BASE_URL: str = ""
    ROOT_CATEGORY_ID: str = "2"
    PAGE_SIZE = 100
    MAX_PAGES = 300  # safety cap per category
    # Some installs' categoryList only exposes thin marketing/nav categories
    # whose product_count sums to a fraction of the real catalog, while the
    # root id itself carries the full flat product assignment directly
    # (verified live: Riba Smith's categoryList children summed to ~280
    # products but products(filter:{category_id:{eq:"2"}}) alone returned
    # 10000). Set True to skip categoryList and paginate the root directly.
    WALK_ROOT_DIRECTLY = False

    custom_settings = _POLITE_SETTINGS

    async def start(self):
        if self.WALK_ROOT_DIRECTLY:
            yield self._page_request(self.ROOT_CATEGORY_ID, 1)
        else:
            yield scrapy.Request(
                self.GRAPHQL_URL,
                method="POST",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {"query": _CATEGORY_LIST_QUERY % self.ROOT_CATEGORY_ID}
                ),
                callback=self.parse_categories,
            )

    def parse_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON categoryList response")
            return
        roots = (data.get("data") or {}).get("categoryList") or []
        children = []
        for root in roots:
            children.extend(root.get("children") or [])
        if not children:
            logger.warning(f"{self.name}: no child categories under root")
            return
        for cat in children:
            cat_id = cat.get("id")
            if cat_id is None:
                continue
            yield self._page_request(str(cat_id), 1)

    def _page_request(self, category_id: str, page: int):
        return scrapy.Request(
            self.GRAPHQL_URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {"query": _PRODUCTS_QUERY % (category_id, self.PAGE_SIZE, page)}
            ),
            callback=self.parse_page,
            meta={"category_id": category_id, "page": page},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON products response")
            return
        block = (data.get("data") or {}).get("products") or {}
        items = block.get("items") or []
        category_id = response.meta["category_id"]
        page = response.meta["page"]
        logger.info(
            f"{self.name}: category={category_id} page={page} count={len(items)}"
        )
        for p in items:
            item = self._item(p)
            if item:
                yield item
        if len(items) >= self.PAGE_SIZE and page < self.MAX_PAGES:
            yield self._page_request(category_id, page + 1)

    def _item(self, p: dict):
        name = (p.get("name") or "").strip()
        price_block = ((p.get("price_range") or {}).get("minimum_price") or {}).get(
            "final_price"
        ) or {}
        value = price_block.get("value")
        if not name or value is None:
            return None
        return {
            "product_id": str(p.get("sku") or ""),
            "product_name": html.unescape(name)[:500],
            "category": None,
            "price": str(value),
            "currency": price_block.get("currency") or self.currency,
            "available": True,
            "url": self.BASE_URL.rstrip("/") + "/" + (p.get("url_key") or ""),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }


_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRICE_RE = re.compile(r'data-price-amount="([0-9.]+)"')
_PRODUCT_BLOCK_RE = re.compile(
    r'<a class="product-item-link"[^>]*href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>'
    r"(?:(?!product-item-link).)*?"
    r'data-price-amount="([0-9.]+)"',
    re.DOTALL,
)


class MagentoSSRBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language, and
    # EITHER START_URLS (a fixed list of category/listing pages) OR
    # DISCOVERY_URL + CATEGORY_URL_RE (a landing page to crawl once, whose
    # matched links become the listing pages to paginate).
    name = None
    START_URLS: list = []
    DISCOVERY_URL: str = ""
    CATEGORY_URL_RE = None  # compiled regex; group(1) is a listing page URL
    PAGE_PARAM = "p"
    MAX_PAGES = 100  # safety cap per listing

    custom_settings = _POLITE_SETTINGS

    async def start(self):
        if self.DISCOVERY_URL:
            yield scrapy.Request(self.DISCOVERY_URL, callback=self.parse_discovery)
        else:
            for url in self.START_URLS:
                yield scrapy.Request(
                    url, callback=self.parse_listing, meta={"page": 1, "base": url}
                )

    def parse_discovery(self, response):
        urls = sorted(set(self.CATEGORY_URL_RE.findall(response.text)))
        logger.info(f"{self.name}: discovered {len(urls)} listing pages")
        for u in urls:
            full = response.urljoin(u)
            yield scrapy.Request(
                full, callback=self.parse_listing, meta={"page": 1, "base": full}
            )

    def parse_listing(self, response):
        body = response.text
        page = response.meta["page"]
        matches = _PRODUCT_BLOCK_RE.findall(body)
        logger.info(f"{self.name}: {response.url} page={page} matches={len(matches)}")
        for url, name, price in matches:
            item = self._item(url, name, price)
            if item:
                yield item
        if matches and page < self.MAX_PAGES:
            base = response.meta["base"]
            sep = "&" if "?" in base else "?"
            nxt = page + 1
            yield scrapy.Request(
                f"{base}{sep}{self.PAGE_PARAM}={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base},
            )

    def _item(self, url: str, name: str, price: str):
        name = name.strip()
        if not name or not price:
            return None
        return {
            "product_id": url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": html.unescape(name)[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }


class MagentoRestBaseSpider(scrapy.Spider):
    """
    Walks the unauthenticated REST surface: /rest/V1/products with
    searchCriteria[pageSize]/[currentPage] (bracket chars URL-encoded).
    Most installs 401 this without a bearer token; use only where a probe
    confirmed it is open (checked live before scaffolding — the more common
    case needs MagentoGraphQLBaseSpider instead).
    """

    # Subclasses MUST set: name, allowed_domains, currency, language,
    # BASE_URL (scheme+host, no trailing slash).
    name = None
    BASE_URL: str = ""
    PAGE_SIZE = 200
    MAX_PAGES = 300  # safety cap

    custom_settings = _POLITE_SETTINGS

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page: int):
        url = (
            f"{self.BASE_URL}/rest/V1/products"
            f"?searchCriteria%5BpageSize%5D={self.PAGE_SIZE}"
            f"&searchCriteria%5BcurrentPage%5D={page}"
        )
        # Without an explicit Accept header, this REST surface content-
        # negotiates against the browser-like Accept string that curl_cffi's
        # impersonation sends and returns XML instead of JSON.
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"page": page},
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        items = data.get("items") or []
        page = response.meta["page"]
        logger.info(f"{self.name}: page={page} count={len(items)}")
        for p in items:
            item = self._item(p)
            if item:
                yield item
        if len(items) >= self.PAGE_SIZE and page < self.MAX_PAGES:
            yield self._page_request(page + 1)

    def _item(self, p: dict):
        name = (p.get("name") or "").strip()
        price = p.get("price")
        if not name or price is None:
            return None
        url_key = next(
            (
                a.get("value")
                for a in p.get("custom_attributes") or []
                if a.get("attribute_code") == "url_key"
            ),
            None,
        )
        return {
            "product_id": str(p.get("sku") or p.get("id") or ""),
            "product_name": html.unescape(name)[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{self.BASE_URL}/{url_key}.html" if url_key else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }


# --- Archived-HTML replay (backfill) -----------------------------------
#
# All three bases above scrape a *live* API surface (GraphQL, REST, or
# server-rendered listing pages), but what Common Crawl / Wayback actually
# archived is the storefront's Luma-theme product-detail HTML sitting behind
# those APIs -- the same surface regardless of which base a given subclass
# uses. So one parser, not three, covers them; each class below just gets it
# assigned as its `parse_html` classmethod (see module docstring in
# `..archived` and `prices.backfill._load_spider_parse_html`).
#
# Measured against 90 archived Magento product-detail pages across 10
# sources spanning both bases with real archived HTML (GraphQL: carrefour_tn,
# dismac_bo, kaynoo_sn, nacional_do, panafoto_pa, gourmet_egypt; SSR:
# coolmarket_jm, gollo_cr, lacuracaonline_ni, riteway_vg, virtualmart_jm):
# JSON-LD + OpenGraph meta (the shared `..archived` tiers) alone accounted
# for 100% of extractable rows once gated by Magento's own
# `product-info-main` marker to reject category/CMS/login pages that carry
# stray OG price meta (a false-positive source found on dismac_bo's landing
# pages). No sample page needed the DOM fallback below; it stays in as the
# documented last resort for an install where neither shared tier fires.

# Magento's canonical price markup: `data-price-amount="X" data-price-type=
# "finalPrice"` -- the currently-charged price, already netting out any
# active special/tier price, as opposed to the struck-through regular price.
_FINAL_PRICE_RE = re.compile(
    r'data-price-amount="([0-9.,]+)"[^>]*data-price-type="finalPrice"', re.DOTALL
)


def _first_itemprop(html_text: str, prop: str):
    m = re.search(rf'itemprop="{prop}"[^>]*>([^<]+)<', html_text)
    return html.unescape(m.group(1)).strip() if m else None


def _magento_dom_row(html_text: str, url: str):
    """Last-resort read of Magento's own PDP markup: `.page-title span.base`
    (`itemprop="name"`), `[data-price-amount][data-price-type="finalPrice"]`,
    and `[itemprop=sku]` / `.product.attribute.sku .value`.
    """
    name = _first_itemprop(html_text, "name")
    if not name:
        return None
    price_m = _FINAL_PRICE_RE.search(html_text) or _PRICE_RE.search(html_text)
    price = normalize_price(price_m.group(1)) if price_m else None
    if not price:
        return None
    row = {"product_name": name[:500], "price": price, "url": url}
    sku = _first_itemprop(html_text, "sku")
    if sku:
        row["product_id"] = sku
    return row


def _magento_parse_html(cls, html_text: str, url: str):
    """Archived Magento storefront HTML -> price rows. See module note above.

    JSON-LD (`rows_from_jsonld`) is tried first and trusted outright -- it
    already type-checks `@type: Product` and requires a name + price, so it
    does not need the `product-info-main` gate below. Only once it comes back
    empty do we check that gate before falling through to OpenGraph meta or
    the raw DOM: without it, Magento's landing/category pages routinely leak
    a stray `product:price:amount` meta tag (verified on dismac_bo) that
    `row_from_meta` would otherwise read as a real product.
    """
    rows = rows_from_jsonld(html_text, url)
    if not rows:
        if "product-info-main" not in html_text:
            return
        row = row_from_meta(html_text, url) or _magento_dom_row(html_text, url)
        rows = [row] if row else []
    for row in rows:
        try:
            if float(row.get("price")) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        yield row


MagentoGraphQLBaseSpider.parse_html = classmethod(_magento_parse_html)
MagentoSSRBaseSpider.parse_html = classmethod(_magento_parse_html)
MagentoRestBaseSpider.parse_html = classmethod(_magento_parse_html)
