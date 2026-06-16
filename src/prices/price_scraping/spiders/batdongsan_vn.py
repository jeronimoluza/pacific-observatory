"""batdongsan.com.vn — rental listings (COICOP 04.1.1).

Separate platform from the PropertyGuru family — server-side rendered, no
Next.js blob, different card markup. The rental landing
``/nha-dat-cho-thue`` paginates as ``/nha-dat-cho-thue/p<N>`` (last page is
``p1913`` at time of writing, so the corpus is ~38k listings; we scrape a
configurable first ``max_pages`` for a CPI-relevant sample).

Cards: ``div.js__card.js__card-listing`` (~20 per page). Price is on
``div.re__card-config-price``, formats:

  * ``20 triệu/tháng``    → 20,000,000 VND/month
  * ``25.5triệu/tháng``   → 25,500,000 VND/month (no space, decimal dot)
  * ``1,5 triệu/tháng``   → 1,500,000 VND/month (Vietnamese decimal comma)
  * ``2 tỷ/tháng``        → 2,000,000,000 VND/month (rare for rent)
  * ``Giá thỏa thuận``    → "negotiable" — skip

Cloudflare bypass: curl_cffi ``safari17_0`` (chrome120 returns 403 on the
rental landing as of 2026-05-21; safari17_0 passes cleanly).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

# /<area-slug>/<title-slug>-pr<digits> — the trailing pr<digits> is the listing id.
_PDP_RE = re.compile(r"-pr(\d{6,})$")
_PRICE_TRIEU_RE = re.compile(r"([\d.,]+)\s*triệu(?:/tháng)?", re.IGNORECASE)
_PRICE_TY_RE = re.compile(r"([\d.,]+)\s*tỷ(?:/tháng)?", re.IGNORECASE)


class BatdongsanVNSpider(scrapy.Spider):
    name = "batdongsan_vn"
    allowed_domains = ["batdongsan.com.vn"]
    currency = "VND"
    language = "vi"

    LANDING_URL = "https://batdongsan.com.vn/nha-dat-cho-thue"
    IMPERSONATE_PROFILE = "safari17_0"

    # First N pages of the rental landing. Each page ~20 cards, so default of
    # 25 gives ~500 listings — matches the ~500–600/run ballpark of the SG twin.
    max_pages = 25

    # CF rate-limits bursts: 3+ pages in parallel triggers 403, and even with
    # single-flight pacing a fraction of paged requests still come back 403.
    # The 403s are intermittent rather than permanent — retrying with a small
    # backoff recovers them, so we add 403 to the retry-code set.
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.max_pages = int(kwargs.get("max_pages", self.max_pages))
        except (TypeError, ValueError):
            pass
        self.scraped_listing_ids: set[str] = set()

    async def start(self):
        for page in range(1, self.max_pages + 1):
            path = self.LANDING_URL if page == 1 else f"{self.LANDING_URL}/p{page}"
            yield scrapy.Request(
                path,
                callback=self.parse_listing_page,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "page_label": f"p{page}",
                },
                errback=self.errback,
            )

    def parse_listing_page(self, response):
        cards = response.css("div.js__card.js__card-listing")
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response.url, scraped_at)
            if item is None:
                continue
            yield item
            emitted += 1
        logger.info(
            "page=%s cards=%d items=%d cumulative=%d",
            response.meta["page_label"],
            len(cards),
            emitted,
            len(self.scraped_listing_ids),
        )

    def _parse_card(self, card, base_url: str, scraped_at: str) -> dict | None:
        href = card.css("a::attr(href)").get()
        if not href:
            return None
        pdp_url = href if href.startswith("http") else urljoin(base_url, href)
        m = _PDP_RE.search(pdp_url)
        if not m:
            return None
        listing_id = m.group(1)
        if listing_id in self.scraped_listing_ids:
            return None

        price_text = " ".join(
            card.css(".re__card-config-price ::text").getall()
        ).strip()
        rent_vnd = self._parse_price_to_vnd(price_text)
        if rent_vnd is None:
            return None

        self.scraped_listing_ids.add(listing_id)

        area = (card.css(".re__card-config-area ::text").get() or "").strip() or None
        beds = (card.css(".re__card-config-bedroom ::text").get() or "").strip() or None
        toilets = (
            card.css(".re__card-config-toilet ::text").get() or ""
        ).strip() or None
        location = (
            " ".join(
                t.strip()
                for t in card.css(".re__card-location ::text").getall()
                if t.strip()
            )
            or None
        )
        title = (card.css(".re__card-title ::text").get() or "").strip() or None

        name_parts = [
            title,
            f"{beds}-bed" if beds else None,
            "rental",
            f"at {location}" if location else None,
            area,
            f"{toilets} bath" if toilets else None,
        ]
        product_name = ", ".join(p for p in name_parts if p)

        return {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": "for-rent",
            "price": str(rent_vnd),
            "currency": self.currency,
            "url": pdp_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _parse_price_to_vnd(price_text: str) -> int | None:
        """Vietnamese real-estate prices use 'triệu' (million) and 'tỷ' (billion)
        as unit suffixes. Decimals can be either dot or comma."""
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
        return None

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)
