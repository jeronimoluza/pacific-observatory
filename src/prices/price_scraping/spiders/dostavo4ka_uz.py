"""
Spider for Dostavo4ka (Uzbekistan) — https://dostavo4ka.uz/ru/.

Online grocery / household store serving Samarkand ("Интернет-магазин
продуктов питания в Самарканде"). The storefront runs a PrestaShop
"innovatory" theme on top of a custom Java backend, so the URL scheme is
NOT stock PrestaShop (`/ru/category/<id>/<slug>.html`,
`/ru/product/<id>/<slug>.html`, Spring-Data style
`?page=&size=&sort=sorting,desc` pagination) and `_prestashop_base.py`
cannot be reused. Everything needed is server-rendered in the raw HTML —
no Playwright, no JSON API.

Category discovery is live: `/ru/category.html` lists all 61 categories,
the great majority of them COICOP division 01/02 (овощи и фрукты, мясо,
яйца/молоко, хлеб, бакалея, соки, газированные напитки, шоколадные
изделия, сыры, йогурт, мука, мёд/варенье, восточные сладости, ...).

Card scoping matters: every product is rendered TWICE on the page (a
desktop grid and a mobile grid), so the selector is anchored on
`#js-product-list .innovatoryProductGrid` — that container holds each
product exactly once. Measured: category 105 returns 128 `article.
product-miniature` nodes page-wide but 64 inside the grid, and 64 is the
true category size.

`size=100` is honoured by the backend, so most categories come back in a
single request; page 2 is still requested whenever a page comes back
full, and a spider-wide `seen` set of product ids guards against the
repeated-last-page loop.

Probed live 2026-09-05: category 105 page 1 vs page 2 (size=12) share zero
product ids — genuinely enumerable, not a fixed carousel. Sample rows:
'Огурцы орзу сорт' 10 999 сум; 'Черешня-1кг' 80 000 сум; 'Абрикосы 1 кг'
59 900 сум; 'Арбуз, шт' 105 990 сум. Currency UZS matches countries.yaml.

Parses: listing pages only (PDPs are never fetched — name, price, id and
category are all on the card).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://dostavo4ka.uz"
_CATEGORY_INDEX = f"{_BASE}/ru/category.html"
_PAGE_SIZE = 100
_MAX_PAGES = 40  # safety cap per category

_CATEGORY_HREF_RE = re.compile(r"/ru/category/(\d+)/([a-z0-9\-]+)\.html")
_PRICE_CLEAN_RE = re.compile(r"[^\d,.]")


def _price(raw: str | None) -> str | None:
    """'10 999 сум' -> '10999'. UZS is written without a minor unit."""
    if not raw:
        return None
    s = _PRICE_CLEAN_RE.sub("", raw.replace("\xa0", " ")).replace(",", ".")
    s = s.rstrip(".")
    if not s:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if value <= 0:
        return None
    return str(int(value)) if value.is_integer() else str(value)


class Dostavo4kaUzSpider(scrapy.Spider):
    name = "dostavo4ka_uz"
    allowed_domains = ["dostavo4ka.uz"]
    currency = "UZS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
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
        self.seen: set[str] = set()

    async def start(self):
        yield scrapy.Request(_CATEGORY_INDEX, callback=self.parse_index)

    def _page_url(self, cid: str, slug: str, page: int) -> str:
        return (
            f"{_BASE}/ru/category/{cid}/{slug}.html"
            f"?page={page}&size={_PAGE_SIZE}&sort=sorting,desc"
        )

    def parse_index(self, response):
        cats = sorted(set(_CATEGORY_HREF_RE.findall(response.text)))
        logger.info("dostavo4ka_uz: %d categories discovered", len(cats))
        for cid, slug in cats:
            yield scrapy.Request(
                self._page_url(cid, slug, 1),
                callback=self.parse_category,
                meta={"cid": cid, "slug": slug, "page": 1},
            )

    def parse_category(self, response):
        cid = response.meta["cid"]
        slug = response.meta["slug"]
        page = response.meta["page"]

        crumbs = [
            t.strip()
            for t in response.css(".breadcrumb ::text").getall()
            if t.strip() and t.strip() not in {"/", ">"}
        ]
        category = crumbs[-1] if crumbs else None

        cards = response.css(
            "#js-product-list .innovatoryProductGrid article.product-miniature"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            pid = card.attrib.get("data-product-id")
            if not pid or pid in self.seen:
                continue
            name = card.css("h2.productName a::text").get()
            price = _price(card.css('span[itemprop="price"]::text').get())
            href = card.css("h2.productName a::attr(href)").get()
            if not name or not price:
                continue
            self.seen.add(pid)
            emitted += 1
            yield {
                "product_id": pid,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            "dostavo4ka_uz: cid=%s page=%s cards=%d new=%d",
            cid,
            page,
            len(cards),
            emitted,
        )

        # A full page means there may be another one. `emitted == 0` means the
        # backend re-served a page we have already banked -- stop either way.
        if len(cards) >= _PAGE_SIZE and emitted and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(cid, slug, nxt),
                callback=self.parse_category,
                meta={"cid": cid, "slug": slug, "page": nxt},
            )
