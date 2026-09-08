"""
Spider for DOZ.pl (Poland — pharmacy chain) — https://www.doz.pl/.

Server-rendered category (/k/<slug>-<id>) pages carry `.product-tile` cards
with clean class-based selectors -- no Playwright needed. `curl_cffi`
chrome124 clears the front page with a plain 200 (no WAF).

Re-verified live 2026-09-06: GET /k/bol-4300 -> 200, 905KB, 24
`.product-tile` cards. Sample: `data-gtm-product-id="202519"` 'DOZ Product
Omega-3 1000, kapsulki miekkie, 60 szt.' price-major "32" + price-minor
"99 zl" -> PLN 32.99.

Price is split into two spans (`.product-tile__price-major` /
`.product-tile__price-minor`, the latter carrying both the decimal digits
and the "zl" unit suffix, e.g. "99 zl") -- joined and regex-cleaned rather
than parsed from one node.

Categories below are ~25 leaf `/k/` category slugs sampled across DOZ's own
homepage nav (every 20th of 509 total), spanning OTC/Rx-adjacent, personal
care, baby, pet, medical devices and vitamins -- not just one shelf.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.doz.pl"

_CATEGORIES = [
    "aparaty-sluchowe-5506",
    "bol-zatok-4303",
    "cukry-i-slodziki-4748",
    "do-oczu-i-rzes-5481",
    "granole-musli-owsianki-4719",
    "higiena-uszu-i-nosa-5245",
    "katar-i-zatoki-4619",
    "kot-5675",
    "lakiery-hybrydowe-5510",
    "maseczki-do-twarzy-4357",
    "na-sen-4957",
    "nietolerancja-laktozy-4611",
    "odtluszczacze-zmywacze-5512",
    "otoskopy-5505",
    "pielegnacja-blizn-5121",
    "platki-pod-oczy-5482",
    "preparaty-witaminowe-5291",
    "pulsoksymetry-5389",
    "smoczki-na-butelke-4563",
    "stetoskopy-5488",
    "termometry-4822",
    "ujedrniajace-4586",
    "witaminy-5484",
    "zaparcia-4607",
    "zestawy-kosmetykow-5561",
]

_MAX_PAGES_PER_CATEGORY = 3
_DIGITS_RE = re.compile(r"\d+")


class DozPlSpider(scrapy.Spider):
    name = "doz_pl"
    allowed_domains = ["doz.pl"]
    currency = "PLN"
    language = "pl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/k/{cat}",
                callback=self.parse_category,
                meta={"cat": cat, "page": 1},
            )

    def parse_category(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        cards = response.css(".product-tile")
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            item = self._item(card, cat, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"doz_pl: {cat} page={page} items={n}")

        if cards and page < _MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/k/{cat}?page={next_page}",
                callback=self.parse_category,
                meta={"cat": cat, "page": next_page},
            )

    def _item(self, card, cat: str, scraped_at: str):
        link = card.css(".product-tile__name-link")
        href = link.attrib.get("href")
        product_id = link.attrib.get("data-gtm-product-id")
        name = link.attrib.get("title") or "".join(
            card.css(".product-tile__name::text").getall()
        ).strip()
        major = card.css(".product-tile__price-major::text").get()
        minor = card.css(".product-tile__price-minor::text").get()
        if not product_id or not name or not major or not minor:
            return None
        minor_digits = "".join(_DIGITS_RE.findall(minor))
        try:
            price = float(f"{major.strip()}.{minor_digits.zfill(2)[:2]}")
        except ValueError:
            return None
        return {
            "product_id": str(product_id),
            "product_name": name.strip()[:500],
            "category": cat.rsplit("-", 1)[0],
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}{href}" if href else f"{_BASE}/k/{cat}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
