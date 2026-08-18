"""
Spider for eMAG Romania — https://www.emag.ro/.

Romania's largest general marketplace (own-stock + third-party sellers,
comparable scale to eBay/Otto — a single mid category like "telefoane-mobile"
alone runs 2931 products / 49 pages). Homepage nav is client-hydrated and the
site fronts a reCAPTCHA badge (anti-fraud only, not blocking — 200 OK
throughout), but plain category listing pages
(`/{slug}/c`, `/{slug}/p{N}/c` for page>=2) are fully server-rendered.

Given the marketplace scale, this is scoped to a fixed, bounded set of
top-level category slugs spanning the main departments rather than a full
site crawl, each capped at MAX_PAGES — see notes in the manifest.

Each product card (`class="card-item card-standard js-product-data"`)
carries a numeric `data-prod-id`, title anchor
(`class="card-v2-title..." data-zone="title"`), canonical `/pd/<CODE>/`
url, and price in `<p class="product-new-price">6&#46;399<sup><small
class="mf-decimal">&#44;</small>99</sup> <span>Lei</span></p>` — Romanian
formatting uses `&#46;` (period) as the thousands separator and `&#44;`
(comma) before the decimal pair, both HTML entities, not literal
punctuation.

Re-verified live 2026-08-17: /telefoane-mobile/c -> 200, 60 cards/page,
2931 products across 49 pages; real product 'Telefon mobil Samsung Galaxy
A17, Dual SIM, 4GB RAM, 128GB, 4G, Black, SM-A175FZKBEUE' RON 849.00 incl.
decimal-formatted variant '6.399,99 Lei' elsewhere on the page (thousands
separator confirmed, not a stray decimal point).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.emag.ro"
_CATEGORY_SLUGS = [
    "telefoane-mobile",
    "laptopuri",
    "televizoare",
    "electrocasnice-mici",
    "carti",
    "jucarii-copii",
    "mobila-living",
    "articole-sport",
    "cosmetice-parfumuri",
    "unelte-gradina",
]
MAX_PAGES = 15

_CARD_SPLIT_RE = re.compile(r'class="card-item card-standard js-product-data')
_NAME_RE = re.compile(r'class="card-v2-title[^"]*"\s*data-zone="title">([^<]+)</a>')
_PRODID_RE = re.compile(r'data-prod-id="(\d+)"')
_URL_RE = re.compile(r'href="(https://www\.emag\.ro/[^"]+/pd/[A-Z0-9]+/)"')
_PRICE_RE = re.compile(
    r'product-new-price">(.*?)<sup><small[^>]*>&#44;</small>(\d+)</sup>'
)
_AVAIL_RE = re.compile(r"text-availability-in_stock")


class EmagRoSpider(scrapy.Spider):
    name = "emag_ro"
    allowed_domains = ["emag.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{_BASE}/{slug}/c",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        html_text = response.text
        starts = [m.start() for m in _CARD_SPLIT_RE.finditer(html_text)]
        starts.append(len(html_text))

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i in range(len(starts) - 1):
            card = html_text[starts[i] : starts[i + 1]]
            name_m = _NAME_RE.search(card)
            prodid_m = _PRODID_RE.search(card)
            url_m = _URL_RE.search(card)
            price_m = _PRICE_RE.search(card)
            if not (name_m and prodid_m and url_m and price_m):
                continue
            whole = re.sub(r"&#\d+;", "", price_m.group(1))
            price = f"{whole}.{price_m.group(2)}"
            n += 1
            yield {
                "product_id": prodid_m.group(1),
                "product_name": html.unescape(name_m.group(1)).strip()[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": bool(_AVAIL_RE.search(card)),
                "url": url_m.group(1),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if n and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}/p{page + 1}/c",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )
