"""
Spider for Doctor OnCall (Malaysia) - https://www.doctoroncall.com.my/

WooCommerce category listings. scrapy-impersonate (safari17_0) reads the
static HTML directly — Playwright is not needed. Each category page renders
28 product cards (section.product) with name, URL, RM price, and product id
visible in the markup.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

# Known top-level WooCommerce categories (slugs under /pharmacy/). Discovery
# can be added later if needed — these 9 cover the full retail catalog.
CATEGORIES = [
    ("health-food-drinks", "Health Food & Drinks"),
    ("vitamins-supplements", "Vitamins & Supplements"),
    ("personal-care", "Personal Care"),
    ("beauty", "Beauty"),
    ("mother-baby", "Mother & Baby"),
    ("medical-devices", "Medical Devices"),
    ("non-prescription-medicines", "Non-Prescription Medicines"),
    ("over-the-counter", "Over-the-Counter"),
    ("prescription-medicines", "Prescription Medicines"),
]

PRICE_RE = re.compile(r"RM\s*([\d,]+(?:\.\d+)?)")


class DoctorOnCallSpider(scrapy.Spider):
    name = "doctor_oncall"
    allowed_domains = ["www.doctoroncall.com.my", "doctoroncall.com.my"]
    currency = "MYR"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_urls: set[str] = set()

    async def start(self):
        for slug, name in CATEGORIES:
            yield self._listing_request(slug, name, 1)

    def _listing_request(self, slug: str, name: str, page: int) -> scrapy.Request:
        url = f"https://www.doctoroncall.com.my/pharmacy/{slug}/"
        if page > 1:
            url = f"https://www.doctoroncall.com.my/pharmacy/{slug}/page/{page}/"
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={
                "impersonate": self.IMPERSONATE_PROFILE,
                "category_slug": slug,
                "category_name": name,
                "page": page,
            },
            errback=self.errback,
        )

    def parse_listing(self, response):
        slug = response.meta["category_slug"]
        name = response.meta["category_name"]
        page = response.meta["page"]

        cards = response.css("section.product")
        items_yielded = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in cards:
            product_id = card.attrib.get("data-product_id")
            product_name = card.css("h3 a::text").get() or card.css("h2 a::text").get()
            href = (
                card.css("h3 a::attr(href)").get() or card.css("h2 a::attr(href)").get()
            )
            if not (product_name and href):
                continue
            product_name = product_name.strip()
            if not product_name:
                continue
            if href in self.scraped_urls:
                continue

            # Card prices live in span/p text — pull the first RM occurrence.
            texts = card.css("span::text, p::text, bdi::text").getall()
            price = None
            for t in texts:
                m = PRICE_RE.search(t)
                if m:
                    price = m.group(1).replace(",", "")
                    break
            if not price:
                continue

            self.scraped_urls.add(href)
            items_yielded += 1
            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": name,
                "price": price,
                "currency": self.currency,
                "url": href,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"category={slug} page={page} cards={len(cards)} yielded={items_yielded}"
        )

        # Pagination — follow "next" if it exists and at least one card landed.
        next_href = response.css("a.next::attr(href)").get()
        if next_href and cards:
            yield self._listing_request(slug, name, page + 1)

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
