"""Zain Sudan prepaid internet bundle tariffs (tariff source, Playwright).

https://www.sd.zain.com/en/prepaid-internet-offers is a SharePoint page whose
package cards (data volume, SDG price, USSD subscription code) are injected
client-side after load -- a plain curl_cffi GET returns the SharePoint shell
with zero pricing text. A default headless-Chromium Playwright context is
403'd by the site's bot filter; a realistic desktop Chrome user agent on the
browser context passes.

Each `.card` on the page holds one bundle: `.internet-package .capacity` /
`.unit` for the data volume, `.price-unit .price .capacity` for the SDG
price, and `.subscription-code` for the USSD dial code (used as product_id
since it's the only stable per-bundle identifier on the page).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

URL = "https://www.sd.zain.com/en/prepaid-internet-offers"
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_CODE_RE = re.compile(r"\*[\d*#]+#")


class ZainPrepaidInternetSdSpider(scrapy.Spider):
    name = "zain_prepaid_internet_sd"
    allowed_domains = ["sd.zain.com"]
    currency = "SDG"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    async def start(self):
        yield scrapy.Request(
            URL,
            callback=self.parse_listing,
            dont_filter=True,
            meta={
                "playwright": True,
                "playwright_context_kwargs": {"user_agent": DESKTOP_UA},
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".internet-package", timeout=30000),
                    PageMethod("wait_for_timeout", 2000),
                ],
            },
        )

    def parse_listing(self, response):
        yielded = 0
        seen_ids = set()
        for card in response.css(".card"):
            capacity = card.css(".internet-package .capacity::text").get()
            unit = card.css(".internet-package .unit::text").get()
            price_raw = card.css(".price-unit .price .capacity::text").get()
            if not (capacity and unit and price_raw):
                continue
            capacity, unit = capacity.strip(), unit.strip()
            price = price_raw.strip().replace(",", "")
            try:
                float(price)
            except ValueError:
                continue

            code_text = " ".join(
                t.strip()
                for t in card.css(".subscription-code *::text").getall()
                if t.strip()
            )
            m = _CODE_RE.search(code_text)
            product_id = m.group(0) if m else f"{capacity}{unit}-{price}"
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            # All 18 bundles live on one physical page. The pipeline's
            # DuplicationPipeline dedups on item['url'] alone, so a plain
            # response.url here would collapse every bundle after the first
            # (see zain_prepaid_internet_sd.py history / prices memory on
            # url-dedup collapsing single-page catalogs). A query param
            # keeps the URL distinct per bundle while still resolving to the
            # same live page for verification.
            bundle_url = f"{response.url}?bundle={quote(product_id, safe='')}"

            yield {
                "product_id": product_id,
                "product_name": f"{capacity} {unit} Prepaid Internet Bundle"[:500],
                "category": "Prepaid Internet",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": bundle_url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info(f"zain_prepaid_internet_sd: yielded {yielded} bundles")
