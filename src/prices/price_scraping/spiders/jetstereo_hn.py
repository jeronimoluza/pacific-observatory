"""
Spider for Jetstereo Honduras -- https://www.jetstereo.com/.

Electronics/appliances/home-goods retailer. Custom Next.js storefront (no
off-the-shelf platform -- not Shopify/WooCommerce/Magento/VTEX). No
`/api/catalog_system/pub/products/search`-style endpoint and no plain
`<script type="application/ld+json">` tag either.

Discovery: `/sitemap.xml` lists all ~6,067 `/product/<slug>` PDP URLs
directly (confirmed live 2026-09-01) -- no category crawl needed.

Extraction: each PDP embeds a schema.org Product block inside a Next.js
React Server Components (RSC) "flight" payload
(`self.__next_f.push([1,"<chunk text>"])`), not as a literal
`<script type="application/ld+json">` tag, so the shared `rows_from_jsonld`
helper does not fire here. Two distinct shapes were found live and BOTH
must be handled -- an earlier version of this spider only handled shape 1
and silently scraped 0 items across ~6,000 requests:

  Shape 1 (short products): the `dangerouslySetInnerHTML.__html` value is
  the Product JSON inlined directly, but double-JSON-stringified (once to
  produce the JSON-LD text, again because the whole RSC element tree is
  itself serialized) -- internal quotes show as `\\\\\\"` (3 backslashes)
  in the raw HTML, while the value's own closing quote shows as `\\"` (1
  backslash), because that boundary belongs to the outer (single) escape
  layer.

  Shape 2 (longer products, e.g. long descriptions): Next.js dedups the
  string into its own chunk and the `__html` value is just a reference,
  `"$4f"` or `"$75"` (hex or decimal chunk id) -- the real content lives
  earlier in the SAME page as a separate `<id>:T<hex-length>,{...}` chunk
  definition, escaped only ONCE (matching the outer layer, not double).

`_extract_product` locates the id-specific `dangerouslySetInnerHTML`
block, resolves a `$<id>` reference to its `<id>:T...,` chunk if present
(searching the WHOLE page -- the chunk definition can appear *before* the
reference), then uses a brace-depth counter (not a regex terminator) to
find the matching closing `}` -- braces are never escaped by JSON string
escaping, so this works unmodified at either escape depth. The captured
span is then unescaped by iteratively JSON-string-unwrapping until it
parses as a dict, which self-adapts to shape 1's double escaping and shape
2's single escaping without hand-counting backslashes.

Live-checked 2026-09-01: plain `requests` (no curl_cffi impersonation
needed) returns 200 with the full payload -- no Cloudflare TLS
fingerprinting on this host, despite the Cloudflare Insights beacon script
present. Currency confirmed HNL from the JSON-LD `priceCurrency` field
(sample: "Batidora de Pedestal KitchenAid" HNL 14995.00).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_HTML_VALUE_RE = re.compile(r'__html\\*":\\*"')
_REF_RE = re.compile(r'\$([0-9a-fA-F]+)\\*"')


def _brace_end(text: str, start: int) -> int:
    """Index just past the `}` that closes the `{` at `text[start]`."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _unescape_iter(s: str, max_iter: int = 4):
    """Undo N layers of JSON-string escaping, whatever N turns out to be."""
    for _ in range(max_iter):
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
        try:
            s = json.loads('"' + s + '"')
        except ValueError:
            return None
    return None


def _extract_product(text: str):
    idx = text.find("ld-json-product-")
    if idx == -1:
        return None
    m1 = _HTML_VALUE_RE.search(text[idx : idx + 300])
    if not m1:
        return None
    value_start = idx + m1.end()

    ref_m = _REF_RE.match(text[value_start : value_start + 30])
    if ref_m:
        # Shape 2: __html is "$<id>" pointing at a "<id>:T<hexlen>,{...}"
        # chunk that can be anywhere in the page (often earlier).
        ref_id = ref_m.group(1)
        chunk_m = re.search(
            r"(?<![0-9a-fA-F])" + re.escape(ref_id) + r":T[0-9a-fA-F]+,", text
        )
        if not chunk_m:
            return None
        content_start = chunk_m.end()
    else:
        content_start = value_start

    if content_start >= len(text) or text[content_start] != "{":
        return None
    end = _brace_end(text, content_start)
    if end == -1:
        return None
    return _unescape_iter(text[content_start:end])


class JetstereoHnSpider(scrapy.Spider):
    name = "jetstereo_hn"
    allowed_domains = ["jetstereo.com", "www.jetstereo.com"]
    currency = "HNL"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 12,
        "DOWNLOAD_DELAY": 0.15,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.jetstereo.com/sitemap.xml", callback=self.parse_sitemap
        )

    def parse_sitemap(self, response):
        urls = re.findall(r"<loc>([^<]+)</loc>", response.text)
        product_urls = sorted({u for u in urls if "/product/" in u})
        logger.info(f"{self.name}: {len(product_urls)} product URLs in sitemap")
        for u in product_urls:
            yield scrapy.Request(u, callback=self.parse_product)

    def parse_product(self, response):
        data = _extract_product(response.text)
        if not data:
            return None

        name = (data.get("name") or "").strip()
        offers = data.get("offers") or {}
        price = offers.get("price")
        if not name or price is None:
            return None

        return {
            "product_id": str(data.get("sku") or ""),
            "product_name": name[:500],
            "category": offers.get("category"),
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in (offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
