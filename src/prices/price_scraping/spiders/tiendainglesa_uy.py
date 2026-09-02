"""
Tienda Inglesa (Uruguay) — https://www.tiendainglesa.com.uy/.

Full-line hypermarket chain, GeneXus/"Hanoi" (com.imasdev.hanoi) storefront
served by ASP.NET. Category and search-result pages embed a real, organic
product grid as inline JSON (`"Product":[...]`) directly in the server
response — no JS execution needed (Tier 1A).

Discovery has two arms, both hitting the same page shape:
  - The 15 top-level department pages
    (/supermercado/categoria/<slug>/<idCategory>), scraped from the
    `vLEVEL1SDTOPTIONS_DESKTOP` nav JSON embedded on /supermercado.
  - One request to /supermercado/busqueda (no query). Verified live: this
    endpoint does NOT actually run a server-side search — every `q=` value
    tried (leche, vino, chocolate, papel higienico, ...) returned the exact
    same 40-item grid (food-heavy: harina, agua mineral, huevos, jamón,
    pizza, ...). It's a generic "featured" fallback list, not per-term
    results, so it is fetched exactly once and labelled "Destacados"
    instead of iterating dozens of fake per-keyword requests. It contributes
    ~40 items not present in any of the 15 department pages.

KNOWN CAP: each page (category or search) renders only its first ~40-45
organic product cards. The embedded facet payload advertises a much larger
`TotalCount` (e.g. 3,207 for Almacen alone), but deeper pages are NOT
reachable by URL: ?page=/?p=/?pagina=/?PageIndex=/?pagesize= are all
silently ignored (verified: identical 41-product JSON on every variant),
and the real pagination + facet/brand narrowing is a stateful GeneXus AJAX
postback (GXAjax), not a GET. This is a first-page-per-slice snapshot, not
a full catalog — breadth comes from walking many distinct
categories/queries rather than depth within one. Row count will be roughly
stable run over run because it is bounded by this fixed slice list, not by
a broken walk.

Prices are plain "$ 1.234" strings (UYU, "." thousands separator, no
decimals observed). CurrencySymbol/CurrencyId in the JSON confirm a single
domestic currency, so `currency` is hardcoded to UYU.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tiendainglesa.com.uy"
NAV_URL = f"{BASE_URL}/supermercado"
FEATURED_URL = f"{BASE_URL}/supermercado/busqueda"

_PRICE_RE = re.compile(r"[^\d,]")


def _extract_json_array(text, key):
    """Pull a `<key>":[...]` JSON array out of a larger non-JSON HTML blob,
    honouring quoted strings so embedded '[' / ']' don't break the scan.
    The GeneXus field name is often prefixed with a per-component instance
    id (e.g. `W0006W00180002vLEVEL1SDTOPTIONS_DESKTOP`), so match on the
    bare key + `":[` suffix rather than requiring a leading quote."""
    marker = f'{key}":['
    start = text.find(marker)
    if start == -1:
        return None
    arr_start = start + len(marker) - 1  # position of the opening '['
    depth = 0
    in_string = False
    escape = False
    i = arr_start
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    raw = text[arr_start:i]
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"tiendainglesa_uy: failed to decode {key!r} JSON block")
        return None


def _extract_products(text):
    return _extract_json_array(text, "Product") or []


def _slugify(name):
    slug = name.lower()
    slug = (
        slug.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "producto"


def _parse_price(raw):
    if not raw:
        return None
    cleaned = _PRICE_RE.sub("", raw)
    # "$ 1.234" thousands-separated integer pesos; no decimal cases observed.
    cleaned = cleaned.replace(".", "").replace(",", ".")
    return cleaned or None


class TiendainglesaUySpider(scrapy.Spider):
    name = "tiendainglesa_uy"
    allowed_domains = ["tiendainglesa.com.uy"]
    currency = "UYU"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(NAV_URL, callback=self.parse_nav, errback=self.errback)

    def parse_nav(self, response):
        categories = (
            _extract_json_array(response.text, "vLEVEL1SDTOPTIONS_DESKTOP") or []
        )

        if not categories:
            logger.warning(
                "tiendainglesa_uy: nav discovery failed, no categories found"
            )

        for cat in categories:
            url = cat.get("url")
            label = cat.get("text") or "categoria"
            if not url:
                continue
            yield response.follow(
                url,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": label},
            )

        yield scrapy.Request(
            FEATURED_URL,
            callback=self.parse_listing,
            errback=self.errback,
            meta={"category": "Destacados"},
        )

    def parse_listing(self, response):
        category = response.meta["category"]
        products = _extract_products(response.text)
        emitted = 0
        for product in products:
            pid = product.get("Id")
            code = product.get("Code")
            name = html.unescape(product.get("Name") or "").strip()
            price = _parse_price(product.get("Price"))
            if not pid or not name or not price:
                continue
            available = not (
                product.get("NotForSaleFlag") or product.get("NotAvailableFlag")
            )
            slug = _slugify(name)
            url = f"{BASE_URL}/supermercado/{slug}.producto?{pid},,{code or ''}"
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": bool(available),
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            emitted += 1

        logger.info(
            f"{self.name}: slice={category!r} emitted={emitted} "
            f"raw_products={len(products)} url={response.url}"
        )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
