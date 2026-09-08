"""
Bruneida.com — https://www.bruneida.com/, Brunei's general classifieds
marketplace ("Free Classified Ads - Brunei").

Discovery lead re-probed 2026-09-06: plain curl_cffi with a realistic
Chrome UA clears the listing pages at 200 with no anti-bot at all, despite
`robots.txt` disallowing `User-agent: *` (repo default `ROBOTSTXT_OBEY =
False` already handles this). Fully server-rendered PHP/jQuery site — no
SPA shell, no API to reverse-engineer.

Page family: listing (category browse pages under /brunei/for-sale/<cat>/,
`?page=N` pagination — confirmed disjoint via "Page 1 of 11" style footers
and distinct product ids page-to-page). The spider never fetches an
individual ad-detail page; everything needed (title, price, url, id) is
already on the category listing card.

Card markup (stable across categories, sampled on mobile-phones and
computers): `<li class="link ...">` containing
`h3.az-title > a[href]` (title + PDP url, trailing `-<digits>` is the ad
id) and `div.az-price` ("$ 30", "$ 1,500", or "&nbsp;" for POA/no-price
ads — skipped). Currency displayed as bare "$" but this is Brunei — BND,
confirmed against seller-typed "Price $30" / "BND" mentions in ad bodies
on the same pages, matching countries.yaml (BND for brunei_darussalam).

Scope: curated "for-sale" (goods) categories only — excludes property,
vehicles, jobs and services, which sit under separate top-level sections
of the site with their own semantics. Categories chosen to span multiple
COICOP divisions (electronics, fashion, health & beauty, home goods)
rather than just one: mobile-phones, computers, electronics,
fashion-clothing, health-beauty, home-garden-stuff.

CAVEAT: these are individual sellers' secondhand-goods asking prices, not
a retailer's posted new-goods price — same caveat as khmer24_kh (KH) and
olx_ba (BA), other general classifieds sources in this repo.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "mobile-phones",
    "computers",
    "electronics",
    "fashion-clothing",
    "health-beauty",
    "home-garden-stuff",
]

MAX_PAGES = 5  # safety cap per category
PRICE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
ID_RE = re.compile(r"-(\d+)$")


class BruneidaBnSpider(scrapy.Spider):
    name = "bruneida_bn"
    allowed_domains = ["bruneida.com"]
    currency = "BND"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                self._url(cat, 1),
                callback=self.parse_page,
                meta={"category": cat, "page": 1},
            )

    @staticmethod
    def _url(category: str, page: int) -> str:
        base = f"https://www.bruneida.com/brunei/for-sale/{category}/"
        return base if page == 1 else f"{base}?&page={page}"

    def parse_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = response.css("li.link")
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            title_a = card.css("h3.az-title a")
            title = title_a.css("::text").get()
            href = title_a.attrib.get("href")
            price_text = card.css("div.az-price::text").get()
            if not (title and href and price_text):
                continue
            m = PRICE_RE.search(price_text)
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            id_m = ID_RE.search(href.rstrip("/"))
            n += 1
            yield {
                "product_id": id_m.group(1) if id_m else None,
                "product_name": title.strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": href,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: category={category} page={page} count={n}")

        if cards and n > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._url(category, nxt),
                callback=self.parse_page,
                meta={"category": category, "page": nxt},
            )
