"""Mitsubishi Eswatini (Stucky Motors) -- https://mitsubishieswatini.co.sz/.

The country's Mitsubishi franchise. WordPress + Elementor, server-rendered,
no WAF (curl_cffi impersonate=chrome124 -> 200, and a bare Scrapy fetch
works too). The homepage carries the full new-vehicle range with a
"Drive away from" price for every model.

Block shape (verified 2026-09-12), one per model inside an Elementor
switcher:
    <div class="bdt-tab-content-item" data-content-id="...xpander...">
      ... <h2 class="elementor-heading-title">Xpander</h2>
      ... <h4 class="elementor-heading-title">Expand your lifestyle</h4>
      ... <div class="elementor-heading-title">Drive away from</div>
      ... <h4 class="elementor-heading-title">E365 995 – E419 995</h4>
      ... <a class="elementor-button" href="/vehicles/xpander/">

PRICE SEMANTICS, stated plainly because it is a real caveat: these are
model-range "drive away from" prices, not per-variant transaction prices.
Eight of the nine models print a RANGE spanning their trim ladder
(Xpander E365 995 - E419 995; Triton E499 990 - E889 990); Xpander Cross
prints a single figure. The spider emits the LOWER bound -- the
"drive away from" figure the page itself advertises -- and records the
upper bound of the range in the product_name suffix so the spread is not
silently lost. A downstream consumer should read these as entry-level
new-car list prices for the model, which is the right granularity for a
COICOP 07.1.1.1 basket anchor and the wrong granularity for SKU-level
stickiness work.

DEDUPLICATION: the Elementor switcher renders the same nine model blocks
FOUR times in the served HTML (desktop tabs, mobile accordion and two
duplicated carousels) -- a naive regex over the page text returns 32
price strings for 8 distinct models plus 1. The spider dedupes on the
model's /vehicles/<slug>/ url, which is stable across the duplicates.

ENUMERABILITY: this is the manufacturer's complete Eswatini range as the
site itself presents it (the nav's "Vehicles" menu lists exactly these
models), not page 1 of a paginated catalog -- so the page1-vs-page2 diff
test is inapplicable. The count is the range.

Currency SZL: the page prints "E" (Emalangeni) with a space as the
thousands separator ("E365 995"), matching countries.yaml's Eswatini
default. Set at class level, never parsed from the symbol. The space
separator is why the price regex accepts spaces inside the number and
strips them -- treating "E365 995" as 365 would be a 1000x error.

Page family: listing only (the homepage block carries model + price + the
model page url; the spider does not fetch /vehicles/<slug>/).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

HOME_URL = "https://mitsubishieswatini.co.sz/"

# "E365 995 – E419 995"  /  "E419 995"
_PRICE_RE = re.compile(r"E\s?(\d[\d\s]{3,})")


def _to_amount(raw: str) -> float | None:
    digits = re.sub(r"\s+", "", raw)
    if not digits.isdigit():
        return None
    value = float(digits)
    return value if value > 0 else None


class MitsubishieswatiniSpider(scrapy.Spider):
    name = "mitsubishieswatini"
    allowed_domains = ["mitsubishieswatini.co.sz"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        seen: set[str] = set()
        blocks = response.css("div.bdt-tab-content-item")
        if not blocks:
            self.logger.error(
                "No div.bdt-tab-content-item blocks on %s -- layout changed",
                response.url,
            )
            return

        for block in blocks:
            model = (block.css("h2.elementor-heading-title::text").get() or "").strip()
            href = block.css(
                'a.elementor-button::attr(href), a.elementor-button-link::attr(href)'
            ).re_first(r"^\S*/vehicles/[^\"']+")
            if not model or not href:
                continue
            url = response.urljoin(href.strip())
            if url in seen:
                continue

            amounts: list[float] = []
            for text in block.css("h4.elementor-heading-title::text").getall():
                if "E" not in text:
                    continue
                for raw in _PRICE_RE.findall(text):
                    value = _to_amount(raw)
                    if value is not None:
                        amounts.append(value)
                if amounts:
                    break
            if not amounts:
                self.logger.warning("No price in block for model %s", model)
                continue

            low = amounts[0]
            name = f"Mitsubishi {model}"
            if len(amounts) > 1 and amounts[-1] != low:
                name = f"{name} (drive-away range to E{amounts[-1]:,.0f})".replace(
                    ",", " "
                )

            seen.add(url)
            yield {
                "product_id": url.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name[:500],
                "category": "New vehicles",
                "price": f"{low:.2f}",
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
