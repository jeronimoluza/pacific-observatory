"""
Spider for Property.com.mm -- https://property.com.mm/

Myanmar rental/sale property portal (Yangon, Mandalay, Naypyidaw focus).
Search is a POST form (`#search_property`, action
`/index.php/en/6/browse`) -- there is no plain GET query-string equivalent
to browse by listing type. Confirmed live 2026-09-06: `v_search_option_4=
Rent` returns a Rent-only result set with a working pagination control, but
the pagination links (`/index.php/frontend/ajax/en/6/<offset>`) are
session-bound and lose the Rent filter when hit as a bare GET (confirmed:
page 2 returned a mixed Rent/Sale set even with a cookie jar carried over
from the POST). Rather than reverse-engineer the session state, this
spider scrapes page 1 of the Rent search only (9 listings confirmed live)
-- comfortably clears the Phase-6 >=5-row gate; deepening pagination is a
documented follow-up, not attempted this pass.

Two-step crawl (listing then PDP) because price is NOT present on the
listing card -- only on the PDP, in a single unambiguous
`<div class="dtlprice">` (a "similar properties" sidebar further down the
PDP also carries `price dtlprice` two-class divs with other listings'
prices, but the exact single-class match always resolves to the FIRST
`.dtlprice` node in document order, which is the page's own property).

Price formats seen on PDPs (mixed currency across listings, same as
ethiopiapropertycentre_et): "120 Lkhs" (MMK, Lakh = 100,000 units -- the
site's own shorthand, not a parsing artifact) and "USD 8000" (US dollars,
used when a landlord/agent quotes in USD). Currency is read per-listing
from which pattern matches, never hardcoded to one value.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://property.com.mm"
_SEARCH_URL = f"{_BASE}/index.php/en/6/browse"

_LKHS_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*Lkhs", re.IGNORECASE)
_USD_RE = re.compile(r"USD\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


class PropertyComMmSpider(scrapy.Spider):
    name = "property_com_mm"
    allowed_domains = ["property.com.mm"]
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "DOWNLOAD_TIMEOUT": 45,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.FormRequest(
            _SEARCH_URL,
            formdata={"v_search_option_4": "Rent"},
            callback=self.parse_listing,
        )

    def parse_listing(self, response):
        cards = response.css("article.aa-single-property")
        logger.info(f"property_com_mm: found {len(cards)} rent listing cards")

        for card in cards:
            href = card.css('a[title="latest properties"]::attr(href)').get()
            if not href:
                href = card.css("a.aa-properties-item-img::attr(href)").get()
            if not href:
                continue
            url = urljoin(_BASE, href)

            # Prefer the element's own text over its `title` attribute: a
            # handful of listings embed literal, unescaped double quotes in
            # their title (e.g. `For "Customers" who want...`), which
            # truncates the `title="..."` ATTRIBUTE at the first embedded
            # quote during HTML parsing (confirmed on listing 5809) while
            # leaving the element's text content intact.
            name = card.css("p.displayaddress strong::text").get()
            if not name:
                name = card.css("p.displayaddress strong::attr(title)").get()
            if not name:
                continue
            name = name.strip()

            category = card.css("p.featured-option_2::text").get()
            category = category.strip() if category else "Residential rental"

            yield scrapy.Request(
                url,
                callback=self.parse_product,
                cb_kwargs={"name": name, "category": category},
            )

    def parse_product(self, response, name, category):
        price_text = response.css("div.dtlprice::text").get()
        if not price_text:
            logger.warning(f"No price found at {response.url}")
            return
        price_text = price_text.strip()

        currency = None
        price = None
        m_usd = _USD_RE.search(price_text)
        m_lkhs = _LKHS_RE.search(price_text)
        if m_usd:
            currency = "USD"
            try:
                price = float(m_usd.group(1).replace(",", ""))
            except ValueError:
                pass
        elif m_lkhs:
            currency = "MMK"
            try:
                price = float(m_lkhs.group(1).replace(",", "")) * 100_000
            except ValueError:
                pass

        if price is None or currency is None or price <= 0:
            logger.warning(f"Could not parse price {price_text!r} at {response.url}")
            return

        product_id = response.url.rstrip("/").split("/property/")[-1].split("/")[0]

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
