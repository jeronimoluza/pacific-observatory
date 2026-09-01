"""MobileCity New Caledonia OPT/Mobilis mobile tariff page."""

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


class MobilecityMobilisNcSpider(scrapy.Spider):
    name = "mobilecity_mobilis_nc"
    allowed_domains = ["mobilecity.nc", "www.mobilecity.nc"]
    start_urls = ["https://www.mobilecity.nc/mobilemania/mobilis/contrats"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, meta={"impersonate_args": {"verify": False}})

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for section in response.css("div.infos"):
            category = self._category(section.attrib.get("id", ""))
            for active_title, price_text, features in self._section_offers(section):
                price_match = _PRICE_RE.search(price_text)
                if not price_match:
                    continue

                variant = self._variant(price_text)
                name = active_title if not variant else f"{active_title} - {variant}"
                price = price_match.group(1).replace(" ", "")
                product_id = _slug(f"{name}-{price}")
                if product_id in seen:
                    continue
                seen.add(product_id)

                yield {
                    "product_id": product_id,
                    "product_name": f"MobileCity Mobilis {name}"[:500],
                    "category": category,
                    "price": price,
                    "price_text": price_text,
                    "currency": self.currency,
                    "available": True,
                    "unit": "per month" if "mois" in price_text.lower() else "tariff",
                    "plan_features": " | ".join(features) or None,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

    @staticmethod
    def _section_offers(section):
        active_title = None
        price_texts: list[str] = []
        features: list[str] = []

        def flush():
            if not active_title:
                return []
            return [
                (active_title, price_text, features)
                for price_text in price_texts
                if price_text
            ]

        for node in section.xpath("./*"):
            tag = node.root.tag.lower()
            if tag == "h2":
                yield from flush()
                active_title = _clean(" ".join(node.css("::text").getall()))
                price_texts = []
                features = []
                continue
            if tag == "h3" and active_title:
                price_texts.append(_clean(" ".join(node.css("::text").getall())))
                continue
            if tag == "ul" and active_title:
                features = [
                    _clean(" ".join(li.css("::text").getall())) for li in node.css("li")
                ]
                features = [item for item in features if item]

        yield from flush()

    @staticmethod
    def _category(section_id: str) -> str:
        if "bloque" in section_id:
            return "Mobile blocked-plan tariff"
        if "data" in section_id:
            return "Mobile data tariff"
        return "Mobile postpaid tariff"

    @staticmethod
    def _variant(price_text: str) -> str:
        lowered = price_text.lower()
        if "data seul" in lowered:
            return "data seul"
        if "option sur forfait" in lowered:
            return "option sur forfait bloque"
        return ""
