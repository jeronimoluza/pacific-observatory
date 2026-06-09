import re
import logging
from urllib.parse import urljoin
import scrapy

logger = logging.getLogger(__name__)

_AREA_RE = re.compile(r"([\d.]+)m")
_LAYOUT_RE = re.compile(r"^([^\d<]+)")


class HomesJpSpider(scrapy.Spider):
    name = "homes_jp"
    allowed_domains = ["www.homes.co.jp"]
    start_urls = ["https://www.homes.co.jp/chintai/tokyo/list/"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "row": "tr.prg-room",
        "listing_id": "::attr(data-kykey)",
        "listing_url": "::attr(data-href)",
        "rent_num": "td.price span.num::text",
        "layout_cell": "td.layout::text",
        "next_page": "a[href*='page=']::attr(href)",
    }

    def parse(self, response):
        rows = response.css(self.SELECTORS["row"])
        logger.info("Found %d room rows on %s", len(rows), response.url)

        for row in rows:
            listing_id = row.css(self.SELECTORS["listing_id"]).get()
            listing_url = row.css(self.SELECTORS["listing_url"]).get()

            rent_raw = row.css(self.SELECTORS["rent_num"]).get()
            if not rent_raw:
                continue
            try:
                rent_yen = int(float(rent_raw) * 10000)
            except ValueError:
                continue

            layout_texts = row.css(self.SELECTORS["layout_cell"]).getall()
            layout = layout_texts[0].strip() if layout_texts else None
            area_sqm = None
            if len(layout_texts) > 1:
                am = _AREA_RE.search(layout_texts[1])
                if am:
                    area_sqm = am.group(1)
            elif layout_texts:
                am = _AREA_RE.search(layout_texts[0])
                if am:
                    area_sqm = am.group(1)

            url = listing_url or response.url
            if listing_id and rent_yen:
                yield {
                    "listing_id": listing_id,
                    "rent_yen_per_month": rent_yen,
                    "layout": layout,
                    "area_sqm": area_sqm,
                    "listing_url": listing_url,
                    "url": url,
                    "currency": self.currency,
                    "language": self.language,
                }

        seen_pages = set()
        for href in response.css(self.SELECTORS["next_page"]).getall():
            full = href if href.startswith("http") else urljoin(response.url, href)
            if full not in seen_pages and full != response.url:
                seen_pages.add(full)
                yield scrapy.Request(full, callback=self.parse)
