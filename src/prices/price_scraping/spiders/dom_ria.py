"""
Spider for DOM.RIA (Ukraine) - dom.ria.com

Apartment rental listings (long-term). Server-rendered Vue/Nuxt SSR — prices
and listing metadata are in the raw HTML, so no Playwright is needed. Listing
cards (`section.realty-item`) carry price, address, rooms and district inline;
no PDP visits required.

Whole source maps to COICOP 04.1.1 (actual rentals paid by tenants). Only
UAH-denominated listings are emitted; USD-quoted listings are skipped to keep
the currency consistent.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class DomRiaSpider(scrapy.Spider):
    name = "dom_ria"
    allowed_domains = ["dom.ria.com"]
    currency = "UAH"

    # Long-term apartment rentals across the largest cities; a few pages each.
    CITIES = ["kiev", "lvov", "odessa", "kharkov", "dnepr"]
    PAGES_PER_CITY = 3
    _BASE = "https://dom.ria.com/uk/arenda-kvartir/{city}/?page={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    _PRICE_RE = re.compile(r"[\d\s ]+")
    _ROOMS_RE = re.compile(r"(\d+)\s*кімнат")
    _ID_RE = re.compile(r"-(\d+)\.html")

    def start_requests(self):
        # Honor start_urls from the YAML/CLI if provided, else build the grid.
        urls = list(getattr(self, "start_urls", []) or [])
        if not urls:
            urls = [
                self._BASE.format(city=c, page=p)
                for c in self.CITIES
                for p in range(1, self.PAGES_PER_CITY + 1)
            ]
        for url in urls:
            city = url.split("/arenda-kvartir/")[-1].split("/")[0] if "/arenda-kvartir/" in url else None
            yield scrapy.Request(url, callback=self.parse_listing, meta={"city": city})

    def parse_listing(self, response):
        city = response.meta.get("city")
        cards = response.css("section.realty-item")
        logger.info("dom_ria: %s -> %d cards", response.url, len(cards))
        for card in cards:
            price_text = card.css("b.size22::text").get() or ""
            if "грн" not in price_text:
                continue  # skip USD-quoted listings
            m = self._PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(0).replace(" ", "").replace(" ", "").strip()
            if not price:
                continue

            href = card.css("div.tit a::attr(href), a.realty-link::attr(href)").get()
            url = response.urljoin(href) if href else response.url
            name = card.css("div.tit a::attr(title)").get()
            if name:
                name = name.strip()
            rooms = card.css("span.point-before::text").re_first(self._ROOMS_RE)
            district = card.css('a[data-level="area"]::text').get()
            district = district.strip() if district else None
            pid = None
            if href:
                idm = self._ID_RE.search(href)
                pid = idm.group(1) if idm else None

            if not name or not price:
                logger.warning("dom_ria: incomplete card at %s", response.url)
                continue

            category_bits = ["Оренда квартир"]
            if city:
                category_bits.append(city)
            if rooms:
                category_bits.append(f"{rooms}-кімнатна")
            if district:
                category_bits.append(district)

            yield {
                "product_id": pid,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category_bits),
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
