"""Zelvendo -- Nadjos Shopping Service (Chad).
https://www.zelvendo.com/boutique/nadjos-shopping-service

Zelvendo is a small Chadian multi-boutique platform (custom PHP, Cloudinary
images); this spider is scoped to the one boutique the candidate list
names. Server-rendered, no API, no sitemap (/sitemap.xml 404s).

Name and price are machine-readable on the add-to-cart button rather than
having to be parsed out of display text:
  <button class="btn-cart" data-id="190" data-nom="Nuisette"
          data-prix="3500.00" data-vendeur-nom="Nadjos Shopping  Service">
`data-prix` is a plain decimal (no minor-unit trap); the rendered card shows
"3 500 FCFA" for the same product, so the two agree.

Pagination is a no-op here: /boutique/<slug>?page=1..5 all re-serve the same
card set (page 3+ are byte-identical), and the page's own counter says 20
products -- i.e. the whole (tiny) catalog fits on one page, the rakhaz_td
situation rather than a broken paginator we could page past. The spider
therefore fetches the boutique page exactly once.

Currency rendered as "FCFA"; XAF per countries.yaml's Chad default.
Page family: listing only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

BOUTIQUE = "https://www.zelvendo.com/boutique/nadjos-shopping-service"


class ZelvendoNadjosTdSpider(scrapy.Spider):
    name = "zelvendo_nadjos_td"
    allowed_domains = ["zelvendo.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(BOUTIQUE, callback=self.parse_listing)

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        seen: set[str] = set()
        for btn in soup.select("button.btn-cart[data-id][data-nom][data-prix]"):
            pid = btn.get("data-id")
            name = (btn.get("data-nom") or "").strip()
            raw = (btn.get("data-prix") or "").strip()
            if not pid or not name or pid in seen:
                continue
            try:
                if float(raw) <= 0:
                    continue
            except ValueError:
                continue
            seen.add(pid)
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": (btn.get("data-vendeur-nom") or "").strip() or None,
                "price": raw,
                "currency": self.currency,
                "available": True,
                "url": f"https://www.zelvendo.com/produit.php?id={pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
