import re
import logging
from urllib.parse import urljoin
import scrapy

logger = logging.getLogger(__name__)

_AREA_RE = re.compile(r"([\d.]+)")


class AnjukeSpider(scrapy.Spider):
    name = "anjuke"
    allowed_domains = ["bj.zu.anjuke.com"]
    start_urls = ["https://bj.zu.anjuke.com/fangyuan/"]
    currency = "CNY"
    language = "zh"

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    SELECTORS = {
        "card": "li.list-item",
        "listing_url": "a.houseInfo::attr(href)",
        "price": "strong.price::text",
        "area": "span.area::text",
        "district": "span.comm-address::text",
        "next_page": "a.next::attr(href)",
    }

    def parse(self, response):
        if response.status in (403, 302) or len(response.text) < 500:
            logger.warning(
                "Fingerprint block on %s (status=%s, len=%d) — Tier 2 candidate",
                response.url,
                response.status,
                len(response.text),
            )
            return

        cards = response.css(self.SELECTORS["card"])
        logger.info("Found %d listing cards on %s", len(cards), response.url)

        for card in cards:
            listing_url = card.css(self.SELECTORS["listing_url"]).get()
            if listing_url and not listing_url.startswith("http"):
                listing_url = urljoin(response.url, listing_url)

            listing_id = None
            if listing_url:
                m = re.search(r"/(\d{6,})", listing_url)
                listing_id = m.group(1) if m else None

            price_raw = card.css(self.SELECTORS["price"]).get(default="")
            try:
                rent_yuan = int(price_raw.strip())
            except ValueError:
                continue

            area_raw = card.css(self.SELECTORS["area"]).get(default="")
            am = _AREA_RE.search(area_raw)
            area_sqm = am.group(1) if am else None

            district = card.css(self.SELECTORS["district"]).get()
            if district:
                district = district.strip()

            url = listing_url or response.url
            yield {
                "listing_id": listing_id,
                "rent_yuan_per_month": rent_yuan,
                "area_sqm": area_sqm,
                "district": district,
                "listing_url": listing_url,
                "url": url,
                "currency": self.currency,
                "language": self.language,
            }

        next_href = response.css(self.SELECTORS["next_page"]).get()
        if next_href:
            full = (
                next_href
                if next_href.startswith("http")
                else urljoin(response.url, next_href)
            )
            yield scrapy.Request(full, callback=self.parse)
