"""Spider for Spesalia (Avellino/Salerno/Napoli, Italy) -- https://spesalia.com/.

PrestaShop storefront on a "tt" theme that does NOT emit schema.org Product
microdata (no `itemtype`/`itemprop`), so the shared `_prestashop_base.py`
(which selects on `[itemtype$="/Product"]`) finds zero items here -- verified
live: 165 category pages, 0 matches. This bespoke spider instead regexes the
theme's actual markup directly: `data-id-product="ID"` on the `<article
class="product-miniature...">` container, followed by
`class="h4 product-title"><a>NAME</a>` and `class="price">PRICE€`.
The /api/products webservice 401s without a key (same as other PrestaShop
installs in this repo), so category discovery reuses the generic
`id-slug` href walk from the homepage/category nav rather than the API.

Re-verified live 2026-08-06: homepage -> 200, 104 real product cards incl.
'RUMMO 88 CASARECCE GR 500' EUR 1,12.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://spesalia.com"
_CATEGORY_HREF_RE = re.compile(r'href="(https?://spesalia\.com/([a-z0-9\-]+)/?)"')
_SKIP_URL_RE = re.compile(
    r"/(cms|content|contatti|connexion|login|carrello|cart|ordine|order|"
    r"note-legali|condizioni|cgv|consegna|ricerca|search|sitemap|"
    r"modulo|account|indirizzo|newsletter)[/-]",
    re.IGNORECASE,
)
_CARD_RE = re.compile(
    r'data-id-product="(\d+)"[^>]*>'
    r'.*?class="h4 product-title"\s*><a[^>]*>([^<]+)</a>'
    r'.*?class="price">([^<]+)</span>',
    re.S,
)
MAX_PAGES = 40


def _normalize_price(raw: str) -> str | None:
    s = raw.replace("\xa0", "").replace("€", "").strip()
    s = s.replace(".", "").replace(",", ".")
    m = re.search(r"\d+(\.\d+)?", s)
    return m.group(0) if m else None


class SpesaliaItSpider(scrapy.Spider):
    name = "spesalia_it"
    allowed_domains = ["spesalia.com"]
    currency = "EUR"
    language = "it"

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/", callback=self.parse_category, meta={"page": 1}
        )

    def _new_category_requests(self, response):
        for url, slug in _CATEGORY_HREF_RE.findall(response.text):
            if slug in self.seen_categories or _SKIP_URL_RE.search(url):
                continue
            self.seen_categories.add(slug)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        n = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (
            response.meta.get("cat_url", response.url).rstrip("/").rsplit("/", 1)[-1]
        )
        for product_id, name, price_raw in cards:
            price = _normalize_price(price_raw)
            if not price:
                continue
            n += 1
            yield {
                "product_id": product_id,
                "product_name": re.sub(r"\s+", " ", name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {response.url} page={page} cards={len(cards)} items={n}"
        )

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if cards and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )
