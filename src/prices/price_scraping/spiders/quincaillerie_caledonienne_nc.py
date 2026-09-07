"""Quincaillerie Caledonienne homepage hardware price cards."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

PRICE_RE = re.compile(r"(.+?)\s+(\d[\d\s\u00a0\u202f]*)\s+TTC\s+Voir la fiche produit", re.I)


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class QuincaillerieCaledonienneNcSpider(scrapy.Spider):
    name = "quincaillerie_caledonienne_nc"
    allowed_domains = ["www.quincaillerie.nc", "quincaillerie.nc"]
    start_urls = ["https://www.quincaillerie.nc/boutique/fr/"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        seen = set()
        for link in response.css("a"):
            text = _clean(link.xpath("string(.)").get())
            match = PRICE_RE.match(text)
            href = link.attrib.get("href")
            if not match or not href:
                continue
            name = _clean(match.group(1))
            price = re.sub(r"\D", "", match.group(2))
            product_id = href.rstrip("/").rsplit("/", 1)[-1].removesuffix(".xhtml")
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "hardware",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": href,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
