import logging
import re
from datetime import datetime, timezone

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"₱\s*([\d,]+(?:\.\d+)?)")
_ID_RE = re.compile(r"/(\d+)-[^/]+\.html$")

CATEGORY_URLS = [
    "https://tgp.com.ph/115-allergy-antihistamine",
    "https://tgp.com.ph/116-antibacterial-anti-infectives",
    "https://tgp.com.ph/117-diabetes",
    "https://tgp.com.ph/118-bladder-prostate",
    "https://tgp.com.ph/119-cardiovascular",
    "https://tgp.com.ph/120-respiratory",
    "https://tgp.com.ph/128-pain-relievers-analgesics",
    "https://tgp.com.ph/129-antivirals",
    "https://tgp.com.ph/131-gastro-antiulcer",
    "https://tgp.com.ph/132-cns",
    "https://tgp.com.ph/133-vitamins-supplements",
    "https://tgp.com.ph/134-dermatologicals",
    "https://tgp.com.ph/135-ophthalmic-otic-nasal",
    "https://tgp.com.ph/136-hormones",
    "https://tgp.com.ph/137-musculoskeletal",
]


class TgpPhSpider(CrawlSpider):
    name = "tgp_ph"
    allowed_domains = ["tgp.com.ph", "www.tgp.com.ph"]
    start_urls = CATEGORY_URLS
    currency = "PHP"
    language = "en"

    SELECTORS = {
        "product_name": "h1.h1::text",
        "price": "span.current-price span::text",
        "product_id": "article.product-miniature::attr(data-id-product)",
        "reference": "div.product-reference span::text",
        "brand": "span.product-brand-name::text",
    }

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/\d+-[a-z0-9-]+\.html$",
                deny=r"(cart|login|account|wishlist|stores|contact)",
            ),
            callback="parse_product",
            follow=False,
        ),
        Rule(
            LinkExtractor(
                allow=r"/\d+-[a-z0-9-]+$",
                deny=r"(order=|cart|login|account|wishlist)",
            ),
            follow=True,
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_ids = set()

    def parse_product(self, response):
        m = _ID_RE.search(response.url)
        if not m:
            return
        product_id = m.group(1)
        if product_id in self.scraped_ids:
            return
        self.scraped_ids.add(product_id)

        product_name = (response.css("h1.h1::text").get() or "").strip()
        price_raw = (
            response.css(
                "span.current-price-value::text, span.current-price span::text"
            ).get()
            or ""
        ).strip()
        pm = _PRICE_RE.search(price_raw)
        if not product_name or not pm:
            return

        price = pm.group(1).replace(",", "")
        reference = (
            response.css("div.product-reference span::text").get() or ""
        ).strip() or None
        brand = (response.css(".product-brand-name::text").get() or "").strip() or None
        breadcrumb = (
            " > ".join(
                t.strip()
                for t in response.css(".breadcrumb li span::text").getall()
                if t.strip()
            )
            or None
        )

        yield {
            "product_id": product_id,
            "product_name": product_name,
            "reference": reference,
            "brand": brand,
            "price": price,
            "currency": self.currency,
            "category": breadcrumb,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)
