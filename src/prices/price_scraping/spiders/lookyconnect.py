"""Spider for Looky Connect (lookyconnect.com) — Tonga's multi-vendor marketplace.

Discovered as lookyconnect.net/tonga/store/<name>/section/<id>/ (Tier 3 handoff
brief). The .net domain now 301s to lookyconnect.com, a rebuilt Next.js platform.
Per the onboarding skill, a marketplace is a directory first — the "Retail"
channel's vendor directory (https://www.lookyconnect.com/to/retail) lists every
first-party Tongan retail vendor with a "Visit Store" link
(/to/retail/vendors/<slug>). Confirmed live 2026-08-11: 6 vendors, ~139 listings
(2 vendors currently show 0 products). "/to/" is the Tonga-locale path prefix
(vs "/nz/" for the New Zealand diaspora-buyer locale) — the whole site
geo-redirects to "/nz" by default from a non-Tongan IP, so URLs are built
explicitly with "/to/" rather than relying on the redirect.

Despite being server-rendered React (Next.js App Router), every vendor page
returns its FULL catalogue in one plain `requests`/curl GET — confirmed
identical between a Playwright-rendered DOM and a raw curl fetch, and the
visible page-number buttons ("2 3 4 5") don't change the response for
`?page=N` (the full list is already server-rendered; no Playwright needed at
scrape time). extraction_pattern: scrapy_html, not scrapy_playwright.

**Currency is set per-item, not at the spider class level** — a deliberate,
documented exception to the usual rule. Each listing's price string carries an
explicit, unambiguous prefix set by the individual seller: "NZ$" (NZD), "A$"
(AUD), or "TOP" (Tonga's own currency, non-breaking-space-separated from the
number, e.g. "TOP\xa065.46"). The SAME vendor mixes prefixes across their own
catalogue (MiyahAnaFekauPou Store: mostly NZ$, one A$ item) — there is no
single class-level constant that would be correct. This mirrors the skill's
"the site returns an explicit currency code" exception, just spread across
`data-testid="price"` text instead of a JSON field. No bare, ambiguous "$" was
observed on any of the 6 vendor pages.

Every vendor's storefront is currently flagged "Store Paused" (orders not
accepted) — this looks like the platform is between launch and go-live, not a
defunct site (fresh uploads dated within the last month, live customer support
chat). Prices are still listed and structurally valid; paused != delisted.
"""

from __future__ import annotations

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_CURRENCY_PREFIXES = [
    ("NZ$", "NZD"),
    ("A$", "AUD"),
    ("TOP", "TOP"),
]
_AMOUNT_RE = re.compile(r"[\d,]+\.?\d*")


def _parse_price(text: str) -> tuple[str | None, float | None]:
    if not text:
        return None, None
    stripped = text.strip()
    for prefix, currency in _CURRENCY_PREFIXES:
        if stripped.startswith(prefix):
            m = _AMOUNT_RE.search(stripped[len(prefix) :])
            if m:
                try:
                    return currency, float(m.group(0).replace(",", ""))
                except ValueError:
                    return None, None
    logger.warning("lookyconnect: unrecognized price prefix %r", stripped)
    return None, None


class LookyconnectSpider(scrapy.Spider):
    """Discovers vendors from the Retail directory, scrapes each vendor's full
    catalogue from a single GET (no pagination needed — SSR embeds everything)."""

    name = "lookyconnect"
    allowed_domains = ["lookyconnect.com"]
    start_urls = ["https://www.lookyconnect.com/to/retail"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
    }

    def parse(self, response):
        vendor_hrefs = response.css("a::attr(href)").re(r"^/to/retail/vendors/[^/?#]+$")
        seen: set[str] = set()
        for href in vendor_hrefs:
            url = response.urljoin(href)
            if url in seen:
                continue
            seen.add(url)
            yield scrapy.Request(url, callback=self.parse_vendor)
        logger.info("lookyconnect: %d vendor(s) discovered", len(seen))

    def parse_vendor(self, response):
        vendor_name = response.css("h1::text").get()
        vendor_name = vendor_name.strip() if vendor_name else None
        cards = response.css("div.product-preview-card")
        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        n = 0
        for card in cards:
            name = card.css('[data-testid="product-title"]::text').get()
            price_text = card.css('[data-testid="price"]::text').get()
            href = card.css("a::attr(href)").get()
            if not name or not price_text:
                continue
            currency, amount = _parse_price(price_text)
            if amount is None:
                continue
            product_id = href.rstrip("/").rsplit("/", 1)[-1] if href else None
            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": amount,
                "currency": currency,
                "url": response.urljoin(href) if href else response.url,
                "category": vendor_name,
                "scraped_at": scraped_at,
            }
            n += 1
        logger.info("lookyconnect: vendor %r -> %d item(s)", vendor_name, n)
