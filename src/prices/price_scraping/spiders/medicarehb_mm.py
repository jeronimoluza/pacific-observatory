"""
Spider for MEDiCARE (Myanmar online pharmacy) -- https://medicarehb.com.mm/

WooCommerce store selling prescription meds, OTC, personal care, skincare,
mother & baby products. Confirmed viable in prior discovery passes (Myanmar
inventory 2026-08-05, known_blockers.md "MEDiCARE is a viable alternative for
COICOP 06").

**Category archive pages (`/?product_cat=<slug>`) are a dead end** -- they
render zero product cards over plain HTTP (confirmed 2026-09-06, repeated
probes): the grid there is populated client-side only (no product markup
anywhere in the static response, despite the page title and sidebar
rendering correctly). The WooCommerce **Store API is not reachable either**
-- `/wp-json/wc/store/v1/products/` 200s but silently serves the homepage
HTML instead of JSON (route not registered / blocked).

**The working surface is WordPress native search**, `/?s=<query>&post_type=
product&paged=N` -- this uses the theme's normal WooCommerce loop template,
which IS server-rendered with full product cards (name, price, category,
product_id all present, no PDP fetch needed). A broad single-letter query
(`s=a`) matches nearly the whole catalog via English/romanized brand and
ingredient names -- confirmed 93 pages of results at ~16-20 cards/page
during a live probe on 2026-09-06. This is the "whole-catalog walk via
overly-broad search" pattern, used here because the category browse surface
is unusable over plain HTTP and this is the closest thing to an enumerable
listing available without Playwright.

**This host is extremely rate-sensitive / flaky**: roughly half of all
plain-curl probes during onboarding returned a bare connection failure
(curl exit 28, 000 status, zero bytes) with no discernible pattern, cleared
on a bare retry seconds later. curl_cffi impersonation made this WORSE (100%
timeout during onboarding) -- this is one of the rare cases where plain
`requests`-style HTTP outperforms browser impersonation, so `DOWNLOAD_HANDLERS`
impersonation is deliberately left at the settings default here rather than
being force-enabled. Settings below are tuned defensively: low concurrency,
a real download delay, and generous retries, because a single in-flight
request failing is normal operation for this host, not a sign of a block.

Card markup (`div.type-product`, verified live 2026-09-06):
  p.name.product-title > a[href="https://.../?product=<slug>"] -> name + url
  span.price .woocommerce-Price-amount bdi -> one or two amounts (sale items
    show <del>original</del> <ins>current</ins>; take the LAST bdi text,
    which is the current/effective price in both the sale and non-sale case)
  p.category -> Burmese category label (kept as-is, not translated)
  [data-product_id] -> stable numeric product id (also embedded in the
    container's own class as "post-<id>", used as a fallback)

Currency: displayed as a trailing "Ks" (Kyat) on every sampled price --
hardcoded MMK per countries.yaml, never parsed from the "Ks" glyph itself.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://medicarehb.com.mm"
_SEARCH_TERM = "a"
_MAX_PAGES = 100
_PRODUCT_ID_RE = re.compile(r"post-(\d+)")


class MedicarehbMmSpider(scrapy.Spider):
    name = "medicarehb_mm"
    allowed_domains = ["medicarehb.com.mm"]
    currency = "MMK"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 4.0,
        "DOWNLOAD_TIMEOUT": 45,
        "RETRY_TIMES": 6,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408],
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 4.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/?s={_SEARCH_TERM}&post_type=product&paged=1",
            callback=self.parse_listing,
            cb_kwargs={"page": 1},
        )

    def parse_listing(self, response, page):
        cards = response.css("div.type-product")
        logger.info(f"medicarehb_mm: page={page} found {len(cards)} cards")
        if not cards:
            return

        for card in cards:
            href = card.css("p.name.product-title a::attr(href)").get()
            name = card.css("p.name.product-title a::text").get()
            if not href or not name:
                continue
            url = urljoin(_BASE, href)
            name = name.strip()

            price_texts = card.css(
                "span.price .woocommerce-Price-amount bdi::text"
            ).getall()
            if not price_texts:
                continue
            raw_price = price_texts[-1].strip()
            try:
                price = float(re.sub(r"[^\d.]", "", raw_price))
            except ValueError:
                continue
            if price <= 0:
                continue

            category = card.css("p.category::text").get()
            category = category.strip() if category else None

            product_id = card.css("[data-product_id]::attr(data-product_id)").get()
            if not product_id:
                cls = card.attrib.get("class", "")
                m = _PRODUCT_ID_RE.search(cls)
                product_id = m.group(1) if m else url.rstrip("/").rsplit("=", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page < _MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/?s={_SEARCH_TERM}&post_type=product&paged={page + 1}",
                callback=self.parse_listing,
                cb_kwargs={"page": page + 1},
            )
