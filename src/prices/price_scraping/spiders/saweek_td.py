"""SAWEEK (Chad) -- https://saweek.com/. Multi-vendor marketplace for
N'Djamena (+235 phone, XAF/FCFA currency selector, vendor shops incl.
Chad Power, Pharma Light, Agro, NECHIVA).

Runs the 6valley (Laravel) multi-vendor storefront. Its REST API
(/api/v1/products/latest) answers `["Unauthorized",401]` without a vendor
key, and /sitemap.xml is misgenerated -- every <loc> points at
`http://localhost/6Valley/product/...` and carries the platform's stock
demo catalog (lorem-ipsum-book, subrtex sofa, timex-marlin), none of which
resolve on saweek.com. The server-rendered listing pages are the only
enumerable surface.

Catalog is genuinely small: /products renders 20 product cards and has no
pagination links at all (?page=2 returns the page with zero cards), which
matches the site's own product count. The three sibling listings
(/latest-products, /discounted-products, /featured-products) are re-cuts of
the same set and are crawled as extra seeds with an in-spider URL dedup, so
the run covers the whole storefront rather than one carousel.

Price: `ins.product__new-price` is the current price ("1,500FCFA"), with
`del.product__old-price` the struck-through was-price -- we take the former.
Currency rendered as "FCFA" only; XAF per countries.yaml's Chad default.

Page family: listing only -- card carries name, price and PDP url; PDPs are
never fetched.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

LISTINGS = [
    "https://saweek.com/products",
    "https://saweek.com/latest-products",
    "https://saweek.com/featured-products",
    "https://saweek.com/discounted-products",
]
_DIGITS = re.compile(r"[\d.,]+")


class SaweekTdSpider(scrapy.Spider):
    name = "saweek_td"
    allowed_domains = ["saweek.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen: set[str] = set()

    async def start(self):
        for url in LISTINGS:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        for card in soup.select("div.product"):
            title = card.select_one("h6.product__title a[href]")
            if not title:
                continue
            url = title.get("href", "")
            if "/product/" not in url:
                continue
            name = title.get_text(" ", strip=True)
            price_el = card.select_one("ins.product__new-price") or card.select_one(
                ".product__price ins"
            )
            if not name or not price_el:
                continue
            m = _DIGITS.search(price_el.get_text(" ", strip=True))
            if not m:
                continue
            price = m.group(0).replace(",", "").rstrip(".")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            if url in self._seen:
                continue
            self._seen.add(url)
            pid_el = card.select_one("[data-product-id]")
            vendor_el = card.select_one(".product__summary .text-muted")
            yield {
                "product_id": pid_el.get("data-product-id") if pid_el else url.rsplit("-", 1)[-1],
                "product_name": name[:500],
                "category": vendor_el.get_text(" ", strip=True) if vendor_el else None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
