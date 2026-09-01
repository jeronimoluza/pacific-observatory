"""Helia New Caledonia mobile plan and prepaid kit prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"([0-9][0-9\s]*)\s*F\b", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class HeliaNcMobileSpider(scrapy.Spider):
    name = "helia_nc_mobile"
    allowed_domains = ["helia.nc", "www.helia.nc"]
    start_urls = [
        "https://www.helia.nc/mobile/forfaits-m",
        "https://www.helia.nc/mobile/kits-prepayes-liberte",
    ]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        source_kind = (
            "Mobile prepaid kit"
            if "kits-prepayes" in response.url
            else "Mobile postpaid plan"
        )
        seen = set()

        for article in response.css("article.node--type-produit"):
            title = _clean(
                " ".join(article.css(".title ::text, .title::text").getall())
            )
            price_text = _clean(
                " ".join(article.css(".price ::text, .price::text").getall())
            )
            price_match = _PRICE_RE.search(price_text)
            if not title or not price_match:
                continue

            features = [
                _clean(" ".join(node.css("::text").getall()))
                for node in article.css(".caracteristiques .wrapper-text")
            ]
            features = [item for item in dict.fromkeys(features) if item]
            price = price_match.group(1).replace(" ", "")
            unit = "per month" if "mois" in price_text.lower() else "prepaid kit"
            key = (source_kind, title.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = _slug(f"{source_kind}-{title}-{price}")

            yield {
                "product_id": product_id,
                "product_name": f"Helia {title}",
                "category": source_kind,
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": unit,
                "plan_features": " | ".join(features) or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
