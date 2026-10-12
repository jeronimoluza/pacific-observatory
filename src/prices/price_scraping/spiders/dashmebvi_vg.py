"""Dash Me BVI (British Virgin Islands) -- https://dashmebvi.com/.

Virgin Gorda-based food and grocery delivery marketplace (default address
Spanish Town, BVI; USD). Multi-vendor Laravel storefront: /vendor/all lists the
vendors, each /vendor/<slug> page embeds a numeric vendor id and a CSRF meta
token, and the menu itself is returned as an HTML fragment (JSON key "html")
by POST /vendor/products/searchResults (needs the session cookie + X-CSRF-TOKEN
+ X-Requested-With). Each .product_row carries the dish/item name and its
$ price; the section heading is the category.

Page family: API (the spider never fetches a PDP; item urls are the permalinks
the fragment links to).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from parsel import Selector

_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


class DashmebviVgSpider(scrapy.Spider):
    name = "dashmebvi_vg"
    allowed_domains = ["dashmebvi.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "COOKIES_ENABLED": True,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request("https://dashmebvi.com/vendor/all", callback=self.parse_vendors)

    def parse_vendors(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            m = re.match(r"https://dashmebvi\.com/vendor/([a-z0-9][a-z0-9-]*)/?$", href)
            if not m or m.group(1) in seen or m.group(1) == "all" or m.group(1).startswith("test-"):
                continue
            seen.add(m.group(1))
            yield scrapy.Request(href, callback=self.parse_vendor_page, meta={"slug": m.group(1)})

    def parse_vendor_page(self, response):
        token = response.css("meta[name='csrf-token']::attr(content)").get()
        vid = re.search(r'vendor:\s*"(\d+)"', response.text)
        if not (token and vid):
            self.logger.warning("no csrf/vendor id on %s", response.url)
            return
        yield scrapy.FormRequest(
            "https://dashmebvi.com/vendor/products/searchResults",
            formdata={
                "tag_id": "",
                "keyword": "",
                "order_type": "featured",
                "vendor": vid.group(1),
                "vendor_category": "",
            },
            headers={
                "X-CSRF-TOKEN": token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": response.url,
                "Accept": "application/json",
            },
            callback=self.parse_menu,
            meta=response.meta,
            dont_filter=True,
        )

    def parse_menu(self, response):
        try:
            html = response.json().get("html") or ""
        except ValueError:
            self.logger.warning("non-JSON menu for %s", response.meta.get("slug"))
            return
        sel = Selector(text=html)
        now = datetime.now(timezone.utc).isoformat()
        for section in sel.css("section.scrolling_section"):
            category = " ".join("".join(section.css("h2.category-head::text").getall()).split())
            category = re.sub(r"\s*\(\d+\)$", "", category) or None
            for row in section.css(".product_row"):
                name = " ".join("".join(row.css("h5.mt-0 ::text").getall()).split())
                price_txt = " ".join(row.css(".product_price ::text").getall())
                pm = _PRICE_RE.search(price_txt)
                url = row.css("a[href*='/product/']::attr(href)").get()
                if not (name and pm and url):
                    continue
                yield {
                    "product_id": row.attrib.get("data-p_sku")
                    or row.css("a.add_vendor_product::attr(data-product_id)").get(),
                    "product_name": name[:500],
                    "price": pm.group(1).replace(",", ""),
                    "currency": self.currency,
                    "category": category,
                    "url": url,
                    "scraped_at": now,
                }
