"""
Spider for Diwak Store Bhutan (https://diwakstore.com/) -- an Odoo-based
department store ("electronics, clothing, homewares, groceries, and more").

Per the hard scope constraint (COICOP 01/02 only), this spider is scoped to
the site's grocery vertical ONLY -- it starts from the top-level
`/shop/category/groceries-5` category, which Odoo's website_sale module
aggregates across every grocery sub-category (bakery, beverages, dairy/eggs,
fruits/vegetables, grains, jar/can goods, legumes, meat/fish, oils/vinegars,
snacks, staples, sweets) on one paginated listing -- verified 2026-09-11
(named leaf categories like groceries-fruits-vegetables-6 return a SUBSET of
the same items). Non-food categories (computers, mobile, fashion, printers,
cameras) are never queued.

Cloudflare/curl_cffi note: the queue's evidence-only notes said "Cloudflare
managed challenge blocked curl" -- re-probed 2026-09-11 with a plain
`requests` GET (no impersonation) plus `verify=False` (self-signed/invalid
chain) and it clears fine; the block was a curl-TLS-fingerprint artifact, not
a live WAF. The project's global RandomBrowserMiddleware still routes every
Scrapy request through curl_cffi impersonation, so `impersonate_args:
{"verify": False}` is set defensively in case this host's cert issue recurs
under that stack.

Pagination: `?page=N`, small catalog (27 grocery items total: 20 on page 1,
7 on page 2, page 3+ re-serves page 2's set verbatim instead of emptying --
the flat-cap trap from the skill's method notes). Stop condition is
therefore "next page's product-URL set == previous page's", not "empty page".

Markup: `div.oe_product` cards; name in
`h2.o_wsale_products_item_title a span`; price in
`div.product_price span.oe_currency_value` (bare number, no currency
symbol -- BTN is fixed at the spider level); PDP link is the card's
`a.oe_product_image_link` href.
"""

import re
from datetime import datetime, timezone

import scrapy

_MAX_PAGES = 15


class DiwakstoreBtSpider(scrapy.Spider):
    name = "diwakstore_bt"
    allowed_domains = ["diwakstore.com"]
    currency = "BTN"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    _META = {"impersonate_args": {"verify": False}}

    def start_requests(self):
        yield scrapy.Request(
            "https://diwakstore.com/shop/category/groceries-5",
            callback=self.parse,
            meta={**self._META, "page": 1, "seen_urls": frozenset()},
        )

    def parse(self, response):
        page = response.meta["page"]
        prev_seen = response.meta["seen_urls"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        cards = response.css("div.oe_product")
        if not cards:
            self.logger.warning(f"No product cards on {response.url}")
            return

        page_urls = set()
        for card in cards:
            link = card.css("a.oe_product_image_link")
            href = link.attrib.get("href") if link else None
            if not href:
                continue
            url = response.urljoin(href)
            page_urls.add(url)

            name = card.css("h2.o_wsale_products_item_title a span::text").get()
            price_text = card.css("div.product_price span.oe_currency_value::text").get()
            if not name or not price_text:
                continue
            price_digits = re.sub(r"[^\d.]", "", price_text)
            if not price_digits:
                continue

            yield {
                "product_id": None,
                "product_name": name.strip(),
                "category": "Groceries",
                "price": float(price_digits),
                "currency": self.currency,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        self.logger.info(f"page={page} cards={len(cards)} urls={len(page_urls)}")

        # Stop when this page repeats the previous page's URL set instead of
        # advancing (the site re-serves its last real page forever rather
        # than returning empty past the end).
        if page_urls and page_urls != prev_seen and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://diwakstore.com/shop/category/groceries-5?page={nxt}",
                callback=self.parse,
                meta={**self._META, "page": nxt, "seen_urls": page_urls},
            )
