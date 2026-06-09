import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_LISTING_ID_RE = re.compile(r"/property/([^/?#]+)")
_PRICE_RE = re.compile(r"₱\s*([\d,]+)")
_SQM_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*sqm", re.IGNORECASE)
_NEXT_RE = re.compile(r"\"price\":\"(\d+)\"")

SEARCH_ROOTS = [
    "https://www.lamudi.com.ph/rent/",
    "https://www.lamudi.com.ph/metro-manila/rent/",
    "https://www.lamudi.com.ph/cebu/rent/",
    "https://www.lamudi.com.ph/davao/rent/",
    "https://www.lamudi.com.ph/laguna/rent/",
]


class LamudiPhSpider(scrapy.Spider):
    name = "lamudi_ph"
    allowed_domains = ["www.lamudi.com.ph", "lamudi.com.ph"]
    currency = "PHP"
    language = "en"

    max_pages = 20

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "HTTPERROR_ALLOWED_CODES": [404, 410],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.max_pages = int(kwargs.get("max_pages", self.max_pages))
        except (TypeError, ValueError):
            pass
        self.scraped_ids = set()

    def start_requests(self):
        for root in SEARCH_ROOTS:
            for page in range(1, self.max_pages + 1):
                url = root if page == 1 else f"{root}?page={page}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_listing_page,
                    meta={"page_label": f"{root}?page={page}"},
                    errback=self.errback,
                )

    def parse_listing_page(self, response):
        snippets = response.css("div.snippet__content")
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for snippet in snippets:
            item = self._parse_snippet(snippet, response.url, scraped_at)
            if item is None:
                continue
            yield item
            emitted += 1
        logger.info(
            "page=%s snippets=%d emitted=%d cumulative=%d",
            response.meta["page_label"],
            len(snippets),
            emitted,
            len(self.scraped_ids),
        )

    def _parse_snippet(self, snippet, base_url, scraped_at):
        href = snippet.css("a::attr(href)").get()
        if not href:
            return None
        listing_url = href if href.startswith("http") else urljoin(base_url, href)
        m = _LISTING_ID_RE.search(listing_url)
        if not m:
            return None
        listing_id = m.group(1)
        if listing_id in self.scraped_ids:
            return None

        price_text = " ".join(
            snippet.css(".snippet__content__price ::text").getall()
        ).strip()
        pm = _PRICE_RE.search(price_text)
        if not pm:
            return None
        price = pm.group(1).replace(",", "")

        self.scraped_ids.add(listing_id)

        title = (snippet.css("h2 ::text, h3 ::text").get() or "").strip() or None
        location = (
            " ".join(
                t.strip()
                for t in snippet.css(".snippet__content__location ::text").getall()
                if t.strip()
            )
            or None
        )
        beds = (snippet.css("[data-test='bedroom']::text").get() or "").strip() or None
        baths = (
            snippet.css("[data-test='bathroom']::text").get() or ""
        ).strip() or None
        area_raw = snippet.css(".property__number.principal-amenity::text").get() or ""
        sqm_m = _SQM_RE.search(area_raw)
        area_sqm = sqm_m.group(1).replace(",", "") if sqm_m else None

        name_parts = [
            f"{beds}-bed" if beds else None,
            "rental",
            f"at {location}" if location else None,
            f"{area_sqm} sqm" if area_sqm else None,
        ]
        product_name = ", ".join(p for p in name_parts if p) or title or listing_id

        return {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": "for-rent",
            "price": price,
            "currency": self.currency,
            "url": listing_url,
            "language": self.language,
            "bedrooms": beds,
            "bathrooms": baths,
            "area_sqm": area_sqm,
            "neighborhood": location,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)
