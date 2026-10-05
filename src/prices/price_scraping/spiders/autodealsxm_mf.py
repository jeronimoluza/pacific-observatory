"""Autodeal Computique SXM (Marigot, Saint-Martin French part) -- https://autodealsxm.com/.

WordPress + Divi + Impleo/ic-epc product catalog (NOT WooCommerce: no Store
API, /wp-json/wc/* is 404). Prices are EUR, rendered "EUR899". Listing:
/produits/page/N/ (12 cards per page, ~31 pages). Listing-only: no PDP fetch.

The repo-wide pinned curl_cffi profile (chrome120) and chrome124 both get a
403 from this host's WAF; safari17_0 and firefox133 clear it (2026-10-05).
Pin safari17_0 and disable the random-profile middleware.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


class AutodealsxmMfSpider(scrapy.Spider):
    name = "autodealsxm_mf"
    allowed_domains = ["autodealsxm.com"]
    currency = "EUR"
    language = "fr"
    max_pages = 60

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "COOKIES_ENABLED": False,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": SAFARI_UA,
    }

    def _req(self, url, page):
        return scrapy.Request(
            url,
            callback=self.parse,
            headers={"User-Agent": SAFARI_UA},
            meta={"impersonate": "safari17_0"},
            cb_kwargs={"page": page},
        )

    async def start(self):
        yield self._req("https://autodealsxm.com/produits/", 1)

    def parse(self, response, page):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.archive-listing")
        for card in cards:
            href = card.css("a::attr(href)").get()
            name = card.css("h3.product-name::text").get()
            price = card.css("span.product-price::text").get()
            if not href or not name or not price:
                continue
            m = re.search(r"(\d[\d.,\s ]*)", price)
            if not m:
                continue
            raw = re.sub(r"[\s ]", "", m.group(1))
            if "," in raw and "." in raw:
                raw = raw.replace(",", "")
            elif "," in raw:
                raw = raw.replace(",", ".")
            try:
                value = float(raw)
            except ValueError:
                continue
            if value <= 0:
                continue
            pid = re.search(r"product-(\d+)", card.attrib.get("class", ""))
            yield {
                "product_id": pid.group(1) if pid else href,
                "product_name": " ".join(name.split())[:500],
                "price": f"{value:.2f}",
                "currency": self.currency,
                "category": None,
                "url": href,
                "language": self.language,
                "store": "Autodeal SXM",
                "scraped_at_utc": scraped_at,
            }
        if cards and page < self.max_pages:
            yield self._req(f"https://autodealsxm.com/produits/page/{page + 1}/", page + 1)
