"""South Sudan electronics catalog from Shopit's public CS-Cart listing pages."""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

import scrapy
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


logger = logging.getLogger(__name__)


_START_URL = "https://shopit.com.ss/electronics/"
_CARD_SEL = "#categories_view_pagination_contents .ut2-gl__item"
_PRODUCT_ID_RE = re.compile(r"sec_discounted_price_(\d+)$")


def _playwright_meta():
    return {
        "playwright": True,
        "playwright_include_page": True,
        "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
    }


class ShopitSsSpider(scrapy.Spider):
    name = "shopit_ss"
    allowed_domains = ["shopit.com.ss", "www.shopit.com.ss"]
    handle_httpstatus_list = [403]
    currency = "USD"
    language = "en"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_listing, meta=_playwright_meta())

    async def parse_listing(self, response):
        page = response.meta.get("playwright_page")
        if page is not None:
            try:
                # A Cloudflare interstitial can satisfy DOMContentLoaded well
                # before the catalog replaces it. Waiting here keeps a timeout
                # from discarding the whole Scrapy request before its callback.
                await page.locator(_CARD_SEL).first.wait_for(
                    state="attached", timeout=45000
                )
                response = response.replace(
                    url=page.url,
                    body=await page.content(),
                    encoding="utf-8",
                )
            except PlaywrightTimeoutError:
                logger.warning(
                    "shopit_ss: no catalog cards after bounded browser wait; url=%s",
                    page.url,
                )
                return
            finally:
                await page.close()

        rendered_cards = len(response.css(_CARD_SEL))
        yielded = 0
        for card in response.css(_CARD_SEL):
            title = (card.css("a.product-title::text").get() or "").strip()
            href = card.css("a.product-title::attr(href)").get()
            price_node = card.css('span[id^="sec_discounted_price_"]')
            price_id = price_node.attrib.get("id", "")
            id_match = _PRODUCT_ID_RE.search(price_id)
            major = (price_node.xpath("./text()[normalize-space()]").get() or "").strip()
            minor = (price_node.css("sup::text").get() or "").strip()

            # Shopit renders cents in a nested <sup>; concatenated text loses
            # the decimal point (for example, "15873" means USD 158.73).
            major = major.replace(",", "")
            if not title or not href or not id_match or not major.isdigit() or not minor.isdigit():
                continue

            yielded += 1
            yield {
                "product_id": id_match.group(1),
                "product_name": title[:500],
                "category": "Electronics & Appliances",
                "price": f"{major}.{minor.zfill(2)}",
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            "shopit_ss: rendered_cards=%d yielded=%d url=%s",
            rendered_cards,
            yielded,
            response.url,
        )

        # The category pagination uses stable /electronics/page-N/ URLs.
        for href in response.css(".ty-pagination a.ty-pagination__item::attr(href)").getall():
            yield response.follow(href, self.parse_listing, meta=_playwright_meta())
