"""
Ramstore do doma (North Macedonia) — https://ramstoredodoma.com.mk/.

Ramstore's grocery-delivery storefront (distinct from ramstore.com.mk, the
brochure-only corporate site which has no online catalog at all). Built on
nopCommerce + the SevenSpikes AjaxFilters plugin ("Emporium" theme).

Category discovery: the homepage's mega-menu links to ~330 single-segment
Cyrillic slugs (e.g. /леб, /сирење-). Each slug 302-redirects to
/search?cid=<N> — a plain GET without JS resolves the numeric category id
from the Location header (confirmed: no Playwright needed at collection
time, only used to discover the mechanism).

Product listing: category pages themselves render an empty AJAX-filter
shell (no product HTML server-side). The real data comes from
POST /Catalog/OBAjaxFilterProducts, form-encoded, with
`PagingFilteringContext[PageNumber]` 1-BASED (not 0) and
`PagingFilteringContext[PageSize]` capped at 100 by the UI's own page-size
options. Verified pagination actually advances: page=1 vs page=2 on the
1,300-product "ХРАНА, СЛАТКИ И СОЛЕНИ ПРОИЗВОДИ" (food/snacks) category
returned disjoint product_id sets (0 overlap of 100/100); page=0 and
page=1 had returned an IDENTICAL set during probing — 0 is not a valid
page number for this endpoint, 1 is the first page.

Prices render as plain "<N> ДЕН" or "<N>,<NN> ДЕН" in span.price.actual-
price (the current/selling price — always present). span.price.old-price
appears only when a discount is active and holds the pre-discount price;
not emitted. No currency_minor_unit trap here — MKD denars are quoted
as whole/decimal units directly in the markup, not smallest-unit integers.
"""

import html
import logging
import re
import urllib.parse
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://ramstoredodoma.com.mk"
PAGE_SIZE = 100
MAX_PAGES = 20  # safety cap per category (2,000 SKUs)

_PRODUCT_RE = re.compile(
    r'<div class="product-item" data-productid="(?P<pid>\d+)">.*?'
    r'<a href="(?P<url>[^"]+)"[^>]*>\s*(?P<name>[^<]+?)\s*</a>\s*</h2>.*?'
    r'<span class="price actual-price">\s*(?P<price>[\d.,]+)\s*&#x434;&#x435;&#x43D;',
    re.S,
)
_CID_RE = re.compile(r"[?&]cid=(\d+)")


def _paging_form(cid: str, title: str, page_number: int) -> dict:
    return {
        "Warning": "",
        "NoResults": "false",
        "q": "",
        "cid": cid,
        "isc": "true",
        "mid": "0",
        "vid": "0",
        "pf": "",
        "pt": "",
        "sid": "true",
        "adv": "true",
        "asv": "false",
        "hmpr": "false",
        "ppr": "false",
        "mev": "false",
        "prp": "false",
        "wsp": "false",
        "crsid": "",
        "Title": title,
        "PagingFilteringContext[PriceRangeFilter][Enabled]": "false",
        "PagingFilteringContext[PriceRangeFilter][RemoveFilterUrl]": "",
        "PagingFilteringContext[SpecificationFilter][Enabled]": "false",
        "PagingFilteringContext[SpecificationFilter][RemoveFilterUrl]": "",
        "PagingFilteringContext[AllowProductSorting]": "false",
        "PagingFilteringContext[AllowProductViewModeChanging]": "false",
        "PagingFilteringContext[AllowCustomersToSelectPageSize]": "false",
        "PagingFilteringContext[OrderBy]": "",
        "PagingFilteringContext[ViewMode]": "",
        "PagingFilteringContext[PageNumber]": str(page_number),
        "PagingFilteringContext[PageSize]": str(PAGE_SIZE),
        "PagingFilteringContext[TotalItems]": "0",
        "PagingFilteringContext[TotalPages]": "0",
        "PagingFilteringContext[FirstItem]": "0",
        "PagingFilteringContext[LastItem]": "0",
        "PagingFilteringContext[HasPreviousPage]": "false",
        "PagingFilteringContext[HasNextPage]": "false",
    }


class RamstoreDoDomaMkSpider(scrapy.Spider):
    name = "ramstore_do_doma_mk"
    allowed_domains = ["ramstoredodoma.com.mk"]
    currency = "MKD"
    language = "mk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_cids: set[str] = set()

    async def start(self):
        yield scrapy.Request(f"{BASE_URL}/", callback=self.parse_home)

    def parse_home(self, response):
        slugs = set(
            m
            for m in response.css("a::attr(href)").getall()
            if m.startswith("/%") and m.count("/") == 1
        )
        logger.info(f"{self.name}: {len(slugs)} candidate category slugs on homepage")
        for slug in slugs:
            name = urllib.parse.unquote(slug.lstrip("/")).strip("-")
            yield scrapy.Request(
                response.urljoin(slug),
                callback=self.parse_category_redirect,
                meta={"category_name": name},
                dont_filter=True,
            )

    def parse_category_redirect(self, response):
        m = _CID_RE.search(response.url)
        if not m:
            return
        cid = m.group(1)
        if cid in self.seen_cids:
            return
        self.seen_cids.add(cid)
        category_name = response.meta["category_name"]
        yield self._page_request(cid, category_name, page_number=1)

    def _page_request(self, cid: str, category_name: str, page_number: int):
        return scrapy.FormRequest(
            f"{BASE_URL}/Catalog/OBAjaxFilterProducts",
            formdata=_paging_form(cid, category_name.upper(), page_number),
            callback=self.parse_products,
            meta={"cid": cid, "category_name": category_name, "page": page_number},
            dont_filter=True,
        )

    def parse_products(self, response):
        cid = response.meta["cid"]
        category_name = response.meta["category_name"]
        page = response.meta["page"]
        matches = list(_PRODUCT_RE.finditer(response.text))
        logger.info(
            f"{self.name}: cid={cid} category={category_name} page={page} "
            f"count={len(matches)}"
        )
        for m in matches:
            price = m.group("price").replace(".", "").replace(",", ".")
            yield {
                "product_id": m.group("pid"),
                "product_name": html.unescape(m.group("name")).strip()[:500],
                "category": category_name,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(m.group("url")),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if len(matches) >= PAGE_SIZE and page < MAX_PAGES:
            yield self._page_request(cid, category_name, page + 1)
