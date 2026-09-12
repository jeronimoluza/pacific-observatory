"""Briteman Services (Eswatini) -- https://britemanservices.com/.

IT / consumer-electronics retailer with stores in Mbabane and Manzini
("Free delivery within Mbabane and Manzini corridors"; WhatsApp order links
carry a +268 number). Bespoke React/Vite SPA -- no WooCommerce, no
Shopify, no catalog API: the whole product list is a plain JS array literal
baked into the static asset bundle at build time, exactly the shape already
handled for busiquip_sz.

Array element shape (verified 2026-09-12, in /assets/index-<hash>.js):
    {img:Ea,name:"Dell XPS 15 (2025)",
     specs:'Processor: i7 · RAM: 16GB · Storage: 1TB SSD · Display: 15.6" OLED',
     price:26500,oldPrice:30500,badge:"-15%",
     category:"Laptops",categorySlug:"laptops",stock:"limited"}

Note `name` and `specs` are quoted with EITHER " or ' (the minifier picks
whichever avoids escaping -- 'MacBook Air M3 13"' uses single quotes), so
the regex accepts both.

GOTCHA, and the reason the spider does not hardcode the bundle URL the way
busiquip_sz does: the Vite content hash in `index-<hash>.js` changes on
every site rebuild. This spider fetches the homepage first and reads the
bundle path out of its `<script>`/`<link>` refs, then scans every
/assets/index-*.js it finds for the product array. Three index-* bundles
are emitted; only one carries the array, and the others are scanned
harmlessly.

ENUMERABILITY, measured 2026-09-12: 16 product objects in the array, 16
distinct names, all 16 carrying a positive integer `price`. This is a
static complete data file rather than a paginated listing, so the
page1-vs-page2 diff does not apply -- the count is the whole catalog, not a
page of it. Cross-check: the pre-rendered homepage HTML links exactly 8
distinct /product/<slug> PDPs (the "featured"/"just in" subset) and its
WhatsApp deep links embed matching prices ("Price: E 12,900" for the iPad
Air M2, price:12900 in the bundle) -- an independent confirmation that the
bundle integers are whole Emalangeni, NOT minor units. No /100 or *100.

PDP urls: the bundle's own slugifier is
  name.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")
reproduced here as `_slugify`. Verified against the links the homepage
actually renders: 'Dell XPS 15 (2025)' -> /product/dell-xps-15-2025 and
'MacBook Air M3 13"' -> /product/macbook-air-m3-13, both present in the
served HTML. As with busiquip_sz the PDP route is client-rendered, so the
url is used only as the row's per-product identity for
DuplicationPipeline's url dedup; the spider never fetches it.

Currency SZL: the homepage's WhatsApp order links print "Price: E 12,900"
(Emalangeni), matching countries.yaml's Eswatini default. Set at class
level, never parsed from the symbol.

Page family: neither listing nor PDP -- a static JS data bundle, with a
per-build filename hash, so there is no stable archive path for this source.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

HOME_URL = "https://britemanservices.com/"

_BUNDLE_RE = re.compile(r"/assets/index-[A-Za-z0-9_\-]+\.js")
_QUOTED = r"""(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')"""
_ITEM_RE = re.compile(
    r"\{img:[A-Za-z0-9_$]+,"
    r"name:(?P<name>" + _QUOTED + r"),"
    r"specs:(?P<specs>" + _QUOTED + r"),"
    r"price:(?P<price>\d+(?:\.\d+)?)"
    r"(?P<tail>[^}]*)\}"
)
_CATEGORY_RE = re.compile(r'category:"([^"]*)"')
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _unquote(raw: str) -> str:
    body = raw[1:-1]
    return re.sub(r"\\(.)", r"\1", body)


def _slugify(name: str) -> str:
    return _SLUG_STRIP_RE.sub("-", name.lower()).strip("-")


class BritemanservicesSpider(scrapy.Spider):
    name = "britemanservices"
    allowed_domains = ["britemanservices.com"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        self._seen: set[str] = set()
        yield scrapy.Request(HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        bundles = sorted(set(_BUNDLE_RE.findall(response.text)))
        if not bundles:
            self.logger.error(
                "No /assets/index-*.js bundle referenced by %s -- the build "
                "layout changed",
                response.url,
            )
            return
        for path in bundles:
            yield scrapy.Request(
                response.urljoin(path),
                callback=self.parse_bundle,
                meta={"bundle": path},
            )

    def parse_bundle(self, response):
        found = 0
        for m in _ITEM_RE.finditer(response.text):
            name = _unquote(m.group("name")).strip()
            if not name:
                continue
            try:
                price = float(m.group("price"))
            except ValueError:
                continue
            if price <= 0:
                continue

            slug = _slugify(name)
            url = f"https://britemanservices.com/product/{slug}"
            if url in self._seen:
                continue
            self._seen.add(url)

            cat_m = _CATEGORY_RE.search(m.group("tail"))
            found += 1
            yield {
                "product_id": slug,
                "product_name": name[:500],
                "category": cat_m.group(1) if cat_m else None,
                "price": m.group("price"),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        self.logger.info("%s -> %d products", response.meta["bundle"], found)
