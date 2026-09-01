"""Spider for KIBO Madagascar -- https://www.kibo.mg/ (Tananarive storefront).

Custom PrestaShop install ("AngarTheme", a multi-boutique setup with separate
store paths /tananarive/, /tanjombato/, /tamatave/, /ivato/). Unlike the
PrestaShop tenants covered by `_prestashop_base.py`, this theme emits NO
schema.org itemprop/itemtype microdata anywhere in the category HTML -- the
base class's container selector (`[itemtype$="/Product"]`) matches zero
elements here, which is exactly the silent-zero failure mode its own
docstring warns about. This spider is a bespoke variant that walks the same
PrestaShop `/{id}-{slug}` clean-URL category convention but extracts from the
theme's actual DOM shape instead: `<article class="product-miniature"
data-id-product="...">` cards, name in `h3.product-title a`, price in
`span.price` (a `span.regular-price` sibling appears only when the item is
discounted -- `.price` always holds the actual charged amount).

Only the Tananarive (capital, largest) storefront is scraped; the other
three store paths mirror the same catalog under a different URL prefix.

Confirmed live 2026-09-01: /tananarive/152-biscuits-sucres-gateaux returns 48
SSR product cards with real MGA prices (e.g. "12 Biscuits Gouty d'or", 1 000
Ar), h1 "Biscuits sucrés, gâteaux" gives the category label, and pagination
follows PrestaShop's standard `?page=N` convention.

Extraction is regex-over-raw-HTML (like leaderprice_mg), not
`response.css()` -- a first pass using CSS/XPath selectors on the parsed DOM
silently returned zero items on several real, card-filled category pages
(confirmed by re-fetching one such page and finding perfectly well-formed
`article.product-miniature` markup by plain-text regex) while working fine
on others. The 700-900KB pages apparently trip something in lxml's
recovery parser upstream of the product grid on some pages. A direct regex
over `response.text` sidesteps the DOM entirely and was verified to recover
100% of cards on every page tested, including discounted cards (matches the
live `.price` span, not the crossed-out `.regular-price`).
"""

import html as html_lib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_HOME_URL = "https://www.kibo.mg/tananarive/"

_CATEGORY_HREF_RE = re.compile(
    r'href="(https://www\.kibo\.mg/tananarive/(\d+)-[a-z0-9\-]+/?)"'
)
_SKIP_URL_RE = re.compile(
    r"/(brand|cms|content|contact|connexion|login|panier|cart|commande|order|"
    r"mentions-legales|conditions|cgv|livraison|recherche|search|sitemap|"
    r"module|compte|account|adresse|newsletter)[/-]",
    re.IGNORECASE,
)
_CARD_RE = re.compile(
    r'<article class="product-miniature[^"]*" data-id-product="(\d+)".*?'
    r'<h3 class="h3 product-title"><a href="([^"]+)">([^<]*(?:<[^/][^>]*>[^<]*)*?)</a>.*?'
    r'<span class="price">([^<]+)</span>',
    re.S,
)
_H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")


def _normalize_price(raw: str) -> str | None:
    if not raw:
        return None
    s = re.sub(r"\s+", "", html_lib.unescape(raw))
    s = s.replace("Ar", "").replace(",", ".").strip()
    try:
        float(s)
    except ValueError:
        return None
    return s


class KiboMgSpider(scrapy.Spider):
    name = "kibo_mg"
    allowed_domains = ["www.kibo.mg", "kibo.mg"]
    currency = "MGA"
    language = "fr"
    MAX_PAGES = 60

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
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
        self.total_items = 0
        self.total_category_pages = 0

    async def start(self):
        self.seen_categories.add("")
        yield scrapy.Request(_HOME_URL, callback=self.parse_category, meta={"page": 1})

    def _new_category_requests(self, response):
        for url, cat_id in _CATEGORY_HREF_RE.findall(response.text):
            if cat_id in self.seen_categories or _SKIP_URL_RE.search(url):
                continue
            self.seen_categories.add(cat_id)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        cards = _CARD_RE.findall(response.text)
        page = response.meta["page"]
        self.total_category_pages += 1
        category = self._category_label(response.text, response.url)
        n = 0
        for product_id, url, name_html, raw_price in cards:
            item = self._item_from_card(product_id, url, name_html, raw_price, category)
            if item:
                n += 1
                yield item
        self.total_items += n
        logger.info(f"kibo_mg: {response.url} page={page} cards={len(cards)} items={n}")

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if cards and page < self.MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )

    def _item_from_card(self, product_id, url, name_html, raw_price, category):
        name = re.sub(r"<[^>]+>", "", name_html)
        name = re.sub(r"\s+", " ", html_lib.unescape(name)).strip()
        if not name:
            return None
        price = _normalize_price(raw_price)
        if not price:
            return None
        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _category_label(self, text, url):
        m = _H1_RE.search(text)
        if m and m.group(1).strip():
            return re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()
        m = re.search(r"/(\d+)-([a-z0-9\-]+)/?$", url.split("?")[0])
        return m.group(2).replace("-", " ") if m else None

    def closed(self, reason):
        if self.total_category_pages and self.total_items == 0:
            logger.error(
                f"kibo_mg: walked {self.total_category_pages} category page(s) across "
                f"{len(self.seen_categories)} categories and emitted ZERO items "
                f"(reason={reason}). Selectors likely stale -- re-probe before shipping."
            )
