"""IB Flavour SL restaurant menu (Freetown, Sierra Leone)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"(?P<amount>\d[\d,./ ]*)\s*Le\b", re.I)
_SKIP = re.compile(r"^(flavor menu|order now|image|big|small|non alcoholic|alcoholic|cocktail|mocktail|rum base shot|break fast|served with.*)$", re.I)
_FILLER_RE = re.compile(r"[.…·_]{2,}")

def _clean(value: str) -> str:
    value = _FILLER_RE.sub(" ", value)
    return " ".join(value.replace("\xa0", " ").split()).strip(" .:-|/")

def _money(value: str) -> str:
    return str(int(float(re.sub(r"[^0-9.]", "", value.replace(",", "")))))

class IbflavorslMenuSpider(scrapy.Spider):
    name = "ibflavorsl_menu"
    allowed_domains = ["ibflavorsl.com"]
    start_urls = ["https://ibflavorsl.com/menu/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0, "AUTOTHROTTLE_ENABLED": True}

    def parse(self, response):
        texts = [_clean(t) for t in response.xpath("//body//text()[not(ancestor::script) and not(ancestor::style)]").getall()]
        seen = set()
        for text in (t for t in texts if t):
            matches = list(_PRICE_RE.finditer(text))
            if not matches:
                continue
            name = _clean(_PRICE_RE.sub("", text))
            if not name or not re.search(r"[A-Za-z]", name) or _SKIP.match(name) or len(name) > 120:
                continue
            for ordinal, match in enumerate(matches, 1):
                price = _money(match.group("amount"))
                key = (name.lower(), price, ordinal)
                if key in seen:
                    continue
                seen.add(key)
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                yield {"product_id": f"{self.name}-{slug}-{price}-{ordinal}", "product_name": f"IB Flavour {name}"[:500], "category": "Restaurant menu item", "price": price, "price_text": match.group(0), "currency": "SLL", "available": True, "unit": "menu item", "url": f"{response.url}#{self.name}-{slug}-{price}-{ordinal}", "language": "en", "scraped_at_utc": datetime.now(timezone.utc).isoformat()}
