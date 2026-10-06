"""KodroMarket -- https://kodromarket.com/ (Bangui classifieds, XAF).

Server-rendered PHP classifieds. Category pages (category.php?slug=...) list
ad.php?id=N links, unpaginated (~65 ads in total). The PDP carries an
`h1.ad-title`, a `.ad-price .deal-price` ("10 950 FCFA") and a breadcrumb.
Ads without a numeric price (job offers, "price on request") are skipped.

Page family: both -- category pages seed PDP urls, rows come from the PDP.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"([\d][\d\s  .,]*)\s*(?:F\s?CFA|FCFA|XAF)", re.I)


class KodromarketCfSpider(scrapy.Spider):
    name = "kodromarket_cf"
    allowed_domains = ["kodromarket.com"]
    currency = "XAF"
    language = "fr"
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request("https://kodromarket.com/", callback=self.parse_home)

    def parse_home(self, response):
        slugs = set(response.css("a::attr(href)").re(r"category\.php\?slug=[a-z0-9-]+"))
        for href in sorted(slugs):
            yield response.follow(href, callback=self.parse_category)

    def parse_category(self, response):
        seen = set()
        for href in response.css("a::attr(href)").re(r"ad\.php\?id=\d+"):
            if href not in seen:
                seen.add(href)
                yield response.follow(href, callback=self.parse_ad)

    def parse_ad(self, response):
        title = (response.css("h1.ad-title::text").get() or "").strip()
        price_txt = " ".join(response.css(".ad-price .deal-price::text").getall())
        m = _PRICE_RE.search(price_txt)
        if not title or not m:
            return
        digits = re.sub(r"\D", "", m.group(1))
        if not digits or int(digits) == 0:
            return
        crumbs = [
            t.strip()
            for t in response.css("nav.km-bc-inline a::text, nav.km-bc-inline span.km-bc-current::text").getall()
            if t.strip()
        ]
        category = " > ".join(crumbs[1:-1]) or None
        ad_id = response.url.split("id=")[-1].split("&")[0]
        yield {
            "product_name": title,
            "price": float(digits),
            "currency": self.currency,
            "url": response.url,
            "product_id": ad_id,
            "category": category,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
