"""
Spider for Sehat.com.pk (Pakistan — online pharmacy) — https://sehat.com.pk/.

Legacy server-rendered PHP storefront (cart.php?action=add&product_id=<id>
add-to-cart links). No WAF -- curl_cffi chrome124 clears every page with a
plain 200.

Re-verified live 2026-09-06: GET
/categories/Consumer-products/Baby-Care/ -> 200, 302KB, 16 `<li>` product
blocks; 10/16 carry a visible price (the other 6 show no price -- likely
out-of-stock or call-for-price items, skipped rather than guessed). Sample:
"Baby Lotion 1's" Rs.1,049.49, product_id=43556 (from the card's
cart.php?...product_id=43556 add-to-cart link). Real pagination confirmed
via ?page=2..6 links present on the category page.

Categories below favour OTC/consumer-goods leaves over Prescription-Drugs-*
leaves -- several Rx categories on this site show no price at all without
an account/prescription upload, which would silently zero out those pages.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://sehat.com.pk"

_CATEGORIES = [
    "Consumer-products/Baby-Care",
    "Consumer-products/Beauty-and-Skin/Bath-soap-and-Hand-wash",
    "Consumer-products/Beauty-and-Skin/Hair-care",
    "Consumer-products/Beauty-and-Skin/Skin-care",
    "Consumer-products/Cosmetics/Perfumes",
    "Consumer-products/Detergents",
    "Consumer-products/Disinfectants",
    "Consumer-products/House-hold-products",
    "Consumer-products/Personal-Hygiene",
    "Consumer-products/Water-purification-products",
    "Over-The-Counter-Drugs/Allergy-and-flu",
    "Over-The-Counter-Drugs/Antiseptics-",
    "Over-The-Counter-Drugs/Constipation",
    "Over-The-Counter-Drugs/Cough",
    "Over-The-Counter-Drugs/Digestion",
    "Over-The-Counter-Drugs/Fever",
    "Over-The-Counter-Drugs/Hair-Care",
    "Over-The-Counter-Drugs/Medicated-Soaps",
    "Over-The-Counter-Drugs/Sun-Block",
    "Antifungal",
]

_MAX_PAGES_PER_CATEGORY = 3
_PID_RE = re.compile(r"product_id=(\d+)")
_PRICE_RE = re.compile(r"[\d,]+\.?\d*")


class SehatPkSpider(scrapy.Spider):
    name = "sehat_pk"
    allowed_domains = ["sehat.com.pk"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/categories/{cat}/",
                callback=self.parse_category,
                meta={"cat": cat, "page": 1},
            )

    def parse_category(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        lis = response.xpath('//li[.//div[contains(@class,"ProductName")]]')
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for li in lis:
            item = self._item(li, cat, response.url, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"sehat_pk: {cat} page={page} items={n}")

        if lis and page < _MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/categories/{cat}/?sort=featured&page={next_page}",
                callback=self.parse_category,
                meta={"cat": cat, "page": next_page},
            )

    def _item(self, li, cat: str, page_url: str, scraped_at: str):
        name = li.css(".ProductName a::text").get()
        price_text = li.css(".ProductPriceRating em::text").get()
        href = li.css(".ProductName a::attr(href)").get()
        pid = li.xpath('.//a[contains(@href,"cart.php")]/@href').re_first(_PID_RE)
        if not name or not price_text or not pid:
            return None
        digits = _PRICE_RE.search(price_text)
        if not digits:
            return None
        try:
            price = float(digits.group().replace(",", ""))
        except ValueError:
            return None
        return {
            "product_id": str(pid),
            "product_name": name.strip()[:500],
            "category": cat.rsplit("/", 1)[-1],
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": urljoin(page_url, href) if href else page_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
