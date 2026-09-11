"""
Spider for MatHaus (Romania), sold via the Bringo delivery marketplace --
https://www.bringo.ro/ro/stores/mathaus/.

Bringo (bringo.ro) is a multi-tenant grocery/retail delivery platform, not a
single retailer -- its sitemap covers dozens of unrelated tenants (Carrefour,
pharmacies, florists, bookstores, butchers, restaurants...) under one domain.
Carrefour is already covered directly via carrefour_ro.py (carrefour.ro,
~38,630 PDP urls) so scraping Carrefour's Bringo listings too would just
duplicate that chain under a delivery markup, which is exactly the kind of
duplication the pipeline's dedup exists to catch. The pharmacy tenants
(farmacia-sensiblu, farmacia-dr-max, help-net) render their PDP with no price,
no add-to-cart form and no `data-afanalytics` block at all (checked 5 pages
across 2 pharmacy tenants, live 2026-09-10) -- looks like the same
"resolve a delivery area / session first" gate documented for other
aggregators in known_blockers.md, not attempted further this pass.

MatHaus (DIY/hardware -- lighting, tools, cables, hardware) is a distinct
Bringo tenant not otherwise covered in the Romania tree, has a clean PDP with
no gating, and has the largest non-duplicate catalog among Bringo's
non-Carrefour tenants (20,164 product urls, confirmed live 2026-09-10:
shards 3/4/5 of the 5-way sharded product sitemap hold 9,398 + 10,088 + 678
MatHaus urls respectively, zero overlap between shards, 0 in shards 1-2).
Source is scoped to `/stores/mathaus/` only; the shard walk still discovers
all 5 `sitemap-generic-product-N.xml` children dynamically via the sitemap
index so a future re-shard doesn't silently drop MatHaus urls.

PDP has NO priceCurrency in its JSON-LD Product node (name/image/description/
brand only -- no `offers` key at all), so this is NOT the standard JSON-LD
price pattern. The real price lives in a `data-afanalytics='{...}'` JSON
attribute on the add-to-cart form
(`{"price":"101,68","currency":"RON","productName":"...","vendorName":"MatHaus",...}`),
cross-verified against the human-visible `<div class="product-price">101,68
RON</div>` on the same page. Falls back to the DOM price div (regex) if the
JS attribute is ever absent, since a handful of sitemap entries are already
stale (404) and either signal being empty on an otherwise-200 page has been
observed to mean "delisted".
"""

import html as ihtml
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.bringo.ro/sitemaps/sitemap-generic-index.xml"
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_PRODUCT_URL_RE = re.compile(r"/stores/mathaus/")
_AF_RE = re.compile(r"data-afanalytics='(\{.*?\})'", re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_PRICE_DIV_RE = re.compile(
    r'class="product-price">\s*(?:De la\s*)?([\d.,]+)\s*RON', re.S
)


def _clean_price(raw: str) -> str | None:
    # Romanian formatting: "1.234,56" -> "1234.56". Sitemap sample prices are
    # all sub-1000 RON so far (no thousands separator observed), but handle
    # it defensively.
    raw = raw.strip()
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return str(float(raw))
    except ValueError:
        return None


class MathausRoSpider(scrapy.Spider):
    name = "mathaus_ro"
    allowed_domains = ["bringo.ro", "www.bringo.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_index)

    def parse_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            if "sitemap-generic-product-" in loc:
                yield scrapy.Request(loc, callback=self.parse_shard)

    def parse_shard(self, response):
        locs = _LOC_RE.findall(response.text)
        product_urls = [u for u in locs if _PRODUCT_URL_RE.search(u)]
        logger.info(
            f"mathaus_ro: shard={response.url} urls={len(locs)} "
            f"mathaus={len(product_urls)}"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        if response.status == 404:
            return

        html_text = response.text
        name = None
        price = None

        m = _AF_RE.search(html_text)
        if m:
            try:
                data = json.loads(ihtml.unescape(m.group(1)))
            except ValueError:
                data = None
            if data:
                name = (data.get("productName") or "").strip() or None
                price = _clean_price(str(data.get("price"))) if data.get("price") else None

        if not name:
            hm = _H1_RE.search(html_text)
            if hm:
                name = re.sub(r"\s+", " ", hm.group(1)).strip() or None

        if not price:
            pm = _PRICE_DIV_RE.search(html_text)
            if pm:
                price = _clean_price(pm.group(1))

        if not name or not price:
            logger.warning(f"mathaus_ro: no name/price at {response.url}")
            return

        yield {
            "product_id": response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name[:500],
            "price": price,
            "currency": self.currency,
            "category": None,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
