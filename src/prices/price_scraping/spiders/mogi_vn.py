import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_LISTING_ID_RE = re.compile(r"id(\d{6,})$")
_PRICE_TRIEU_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*triệu", re.IGNORECASE)
_PRICE_TY_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*tỷ", re.IGNORECASE)
_AREA_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*m(?:<sup>2</sup>|²|2)", re.IGNORECASE)

LANDING_URLS = [
    "https://mogi.vn/thue-nha",
    "https://mogi.vn/cho-thue-can-ho",
    "https://mogi.vn/thue-phong-tro",
]

MAX_PAGES = 20


class MogiVNSpider(scrapy.Spider):
    name = "mogi_vn"
    allowed_domains = ["mogi.vn", "www.mogi.vn"]
    currency = "VND"
    language = "vi"

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
            self.max_pages = int(kwargs.get("max_pages", MAX_PAGES))
        except (TypeError, ValueError):
            self.max_pages = MAX_PAGES
        self.scraped_ids = set()

    async def start(self):
        for base in LANDING_URLS:
            for page in range(1, self.max_pages + 1):
                url = base if page == 1 else f"{base}?cp={page}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_listing_page,
                    meta={"page_label": url},
                    errback=self.errback,
                )

    def parse_listing_page(self, response):
        cards = response.css("li div.prop-info")
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            item = self._parse_card(card, scraped_at)
            if item is None:
                continue
            yield item
            emitted += 1
        logger.info(
            "page=%s cards=%d emitted=%d cumulative=%d",
            response.meta["page_label"],
            len(cards),
            emitted,
            len(self.scraped_ids),
        )

    def _parse_card(self, card, scraped_at):
        href = card.css("a.link-overlay::attr(href)").get()
        if not href:
            return None
        listing_url = (
            href if href.startswith("http") else urljoin("https://mogi.vn", href)
        )
        m = _LISTING_ID_RE.search(listing_url)
        if not m:
            return None
        listing_id = m.group(1)
        if listing_id in self.scraped_ids:
            return None

        title = (card.css("h2.prop-title::text").get() or "").strip()
        price_raw = (card.css("div.price::text").get() or "").strip()
        rent_vnd = self._parse_price_to_vnd(price_raw)
        if rent_vnd is None:
            return None

        self.scraped_ids.add(listing_id)

        address = (card.css("div.prop-addr::text").get() or "").strip() or None
        area_html = card.css("ul.prop-attr li").get() or ""
        area_m = _AREA_RE.search(area_html)
        area_sqm = area_m.group(1).replace(",", "") if area_m else None

        slug_parts = listing_url.rstrip("/").split("/")
        neighborhood = slug_parts[3] if len(slug_parts) > 3 else None

        name_parts = [
            title,
            f"at {address}" if address else None,
            f"{area_sqm} m2" if area_sqm else None,
        ]
        product_name = ", ".join(p for p in name_parts if p) or listing_id

        return {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": "for-rent",
            "price": str(rent_vnd),
            "currency": self.currency,
            "url": listing_url,
            "language": self.language,
            "area_sqm": area_sqm,
            "neighborhood": neighborhood,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _parse_price_to_vnd(price_text):
        if not price_text or "thỏa thuận" in price_text.lower():
            return None
        m = _PRICE_TY_RE.search(price_text)
        if m:
            n = float(m.group(1).replace(",", "."))
            return int(n * 1_000_000_000)
        m = _PRICE_TRIEU_RE.search(price_text)
        if m:
            n = float(m.group(1).replace(",", "."))
            return int(n * 1_000_000)
        digits = re.search(r"([\d]+)", price_text)
        if digits:
            return int(digits.group(1))
        return None

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)
