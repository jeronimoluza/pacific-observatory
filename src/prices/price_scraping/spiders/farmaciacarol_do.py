"""
Farmacia Carol (Dominican Republic) - https://tienda.farmaciacarol.com

The public domain (farmaciacarol.com) is a SharePoint corporate page with no
storefront; the real store is the subdomain tienda.farmaciacarol.com, a
legacy ASP.NET WebForms site. Category slugs are enumerated from
catalog.aspx (212 found 2026-08-17). Each category-list.aspx page
server-renders ~30 products with schema.org-adjacent markup
(RetailPriceValue / tag_url), no impersonation needed.

Pagination is an ASP.NET AJAX UpdatePanel postback (`__doPostBack` on
uxNextLinkButton): plain query-string paging (`?page=2`) does NOT work and
silently redirects to the category's canonical URL instead. The postback
only advances when the FULL original form (all ~100 hidden fields,
including __VIEWSTATE) is replayed with __EVENTTARGET overridden -
confirmed live: page 1 and the resulting page-2 delta return fully disjoint
product sets. Only one extra page per category is fetched (page 1 + page 2)
- deeper pagination past that point is unverified for this session and
skipped rather than risking silent duplicate/garbage pages; a full-catalog
crawl should re-derive further pages' viewstate before trusting them.

Prices are DOP (Dominican Republic's official currency; magnitudes -
hundreds to low thousands of DOP for OTC/skincare items - are consistent
with street pricing, though the site's markup carries no explicit
priceCurrency field to confirm directly).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://tienda.farmaciacarol.com/"
_CATALOG_URL = _BASE + "catalog.aspx"
_CATEGORY_HREF_RE = re.compile(r'href="([^"]*-list\.aspx)"')
_SPLIT_RE = re.compile(r'uxProductQuickView_uxProductHidden" value="(\d+)"')
_TAG_RE = re.compile(r'tag_url="([^"]+)"\s*>\s*([^<]+?)\s*</a>')
_PRICE_RE = re.compile(r'uxPriceLabel"[^>]*>\$?([\d,]+\.\d+)')
_NEXT_TARGET_TPL = (
    "ctl01$ctl00$uxWebsitePlaceHolder$uxPlaceHolder$uxProductList"
    "$uxPagingControl$uxNextLinkButton"
)
_SCRIPT_MANAGER_TPL = (
    "ctl01$ctl00$uxWebsitePlaceHolder$uxPlaceHolder$uxProductList$uxPagingControl"
    "|" + _NEXT_TARGET_TPL
)


def _extract_items(text):
    parts = _SPLIT_RE.split(text)
    ids = parts[1::2]
    chunks = parts[2::2]
    for pid, chunk in zip(ids, chunks):
        tag_m = _TAG_RE.search(chunk)
        if not tag_m:
            continue
        price_m = _PRICE_RE.search(chunk)
        if not price_m:
            continue
        yield pid, tag_m.group(1), tag_m.group(2).strip(), price_m.group(1)


class FarmaciacarolDoSpider(scrapy.Spider):
    name = "farmaciacarol_do"
    allowed_domains = ["farmaciacarol.com"]
    currency = "DOP"
    language = "es"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield scrapy.Request(_CATALOG_URL, callback=self.parse_catalog)

    def parse_catalog(self, response):
        slugs = sorted(set(_CATEGORY_HREF_RE.findall(response.text)))
        logger.info("farmaciacarol_do: %s categories discovered", len(slugs))
        for slug in slugs:
            yield scrapy.Request(
                urljoin(_BASE, slug),
                callback=self.parse_category,
                meta={"page": 1},
            )

    def parse_category(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        found = False
        for pid, tag_url, name, price in _extract_items(response.text):
            found = True
            yield self._build(pid, tag_url, name, price, scraped_at)

        if found and response.meta["page"] == 1:
            yield scrapy.FormRequest.from_response(
                response,
                formdata={
                    "__EVENTTARGET": _NEXT_TARGET_TPL,
                    "__EVENTARGUMENT": "",
                    "ctl01$ctl00$uxScriptManager": _SCRIPT_MANAGER_TPL,
                    "__ASYNCPOST": "true",
                },
                headers={
                    "X-MicrosoftAjax": "Delta=true",
                    "X-Requested-With": "XMLHttpRequest",
                },
                callback=self.parse_category,
                meta={"page": 2},
                dont_filter=True,
            )

    def _build(self, pid, tag_url, name, price, scraped_at):
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": None,
            "price": price.replace(",", ""),
            "currency": self.currency,
            "available": True,
            "url": urljoin(_BASE, tag_url.lstrip("~")),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
