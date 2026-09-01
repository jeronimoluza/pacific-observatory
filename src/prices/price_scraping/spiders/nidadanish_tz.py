"""
Spider for NidaDanish (Tanzania) -- https://www.nidadanish.com/.

Server-rendered CS-Cart storefront ("NidaDanish | Tanzania's Online Store"),
confirmed live 2026-09-01. Runs on CS-Cart's Multi-Vendor edition (theme
config exposes `vendor`/`vendor_plans` blocks and a "Become a seller"
link), but the buyer-facing UI hides vendor identity entirely --
`vendor.show_name_as_link` and `vendor.show_logo` are both "N" in the
embedded theme config, and the `/vendors/` and `/sellers/` directory paths
both 404. There is no way for a shopper (or this spider) to tell which
of possibly-several sellers fulfils a given listing, so rule 14's "split
into named merchants" is not applicable here -- the storefront presents
as ONE general hypermarket, not a browsable marketplace of distinguishable
shops, and is classified `channel: hypermarket` on that basis.

Catalog spans ~600+ categories from large appliances through groceries
(rice-sugar, cooking-oil, etc. all carry real TZS-priced Tanzanian grocery
SKUs, e.g. 'Munawar Premium Mbeya White Rice 5kg' TZS 19,000). Category
start URLs are scraped once from the homepage mega-menu (`<a href=".../"
class="">Name</a>` inside the `ut2-lsl` menu blocks) -- 617 confirmed live.
Each category page is requested with `?items_per_page=128` to avoid
pagination in the common case; a `page=2` link in the response (CS-Cart's
own pagination) is followed up to MAX_PAGES_PER_CATEGORY as a safety net
for categories that exceed 128 SKUs.

Product cards are extracted by splitting the page on each product's
`product_data[<id>][product_id]` hidden input (the CS-Cart internal
numeric product id, stable and unique site-wide -- used as `product_id`),
then reading the `product-title` anchor (href + title attribute -> name)
and the `ty-price-num` price span within that product's chunk. Many SKUs
are sold in bulk packs ("Pack of 400 Pcs") -- this is the site's own
retail unit, not a wholesale-only listing; pack size is left in
`product_name` verbatim per the raw-name convention (the classifier reads
the unmodified name).

Prices are plain-integer TZS with comma thousands separators (e.g.
"19,000") -- comma stripped, no decimal invented, matching the TZS
integer-currency convention for this country.
"""

import html as htmllib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.nidadanish.com"

_CATEGORY_LINK_RE = re.compile(
    r'href="(https://www\.nidadanish\.com/[a-zA-Z0-9-]+/)"\s+class="">([^<]+)</a>'
)
_PRODUCT_ID_RE = re.compile(r'product_data\[(\d+)\]\[product_id\]"\s*value="\d+"\s*/>')
_TITLE_RE = re.compile(r'href="([^"]+)"\s+class="product-title"\s+title="([^"]*)"')
_PRICE_RE = re.compile(r'ty-price-num">([\d,]+)</span>')
_NEXT_PAGE_RE = re.compile(
    r'href="([^"]*[?&]page=(\d+)[^"]*)"[^>]*class="[^"]*ty-pagination'
)

MAX_PAGES_PER_CATEGORY = 10  # safety cap; ~all categories are 1 page at 128/pg


def _clean_name(raw: str) -> str:
    """Fixed-point HTML-unescape (rule 22: entities can double-escape)."""
    prev = raw
    while True:
        nxt = htmllib.unescape(prev)
        if nxt == prev:
            break
        prev = nxt
    return re.sub(r"\s+", " ", prev).strip()


class NidadanishTzSpider(scrapy.Spider):
    name = "nidadanish_tz"
    allowed_domains = ["nidadanish.com"]
    currency = "TZS"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/",
            callback=self.parse_home,
        )

    def parse_home(self, response):
        seen = set()
        n = 0
        for url, name in _CATEGORY_LINK_RE.findall(response.text):
            if url in seen:
                continue
            seen.add(url)
            n += 1
            yield scrapy.Request(
                f"{url}?items_per_page=128",
                callback=self.parse_category,
                meta={"category": _clean_name(name), "page": 1, "category_url": url},
            )
        logger.info("nidadanish_tz discovered %d categories from home menu", n)

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        category_url = response.meta["category_url"]

        text = response.text
        splits = list(_PRODUCT_ID_RE.finditer(text))
        scraped_at = datetime.now(timezone.utc).isoformat()

        count = 0
        for i, m in enumerate(splits):
            pid = m.group(1)
            start = m.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else start + 4000
            chunk = text[start:end]
            tm = _TITLE_RE.search(chunk)
            pm = _PRICE_RE.search(chunk)
            if not (tm and pm):
                continue
            url, raw_name = tm.groups()
            name = _clean_name(raw_name)
            price = pm.group(1).replace(",", "")
            if not name or not price:
                continue
            count += 1
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info("nidadanish_tz category=%s page=%d count=%d", category, page, count)

        if page < MAX_PAGES_PER_CATEGORY:
            for href, pg in _NEXT_PAGE_RE.findall(text):
                if int(pg) == page + 1:
                    next_url = href if href.startswith("http") else f"{_BASE}{href}"
                    yield scrapy.Request(
                        next_url,
                        callback=self.parse_category,
                        meta={
                            "category": category,
                            "page": page + 1,
                            "category_url": category_url,
                        },
                    )
                    break
