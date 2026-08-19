"""
Spider for Prisma Finland (S Group) — https://www.prisma.fi/.

IMPORTANT SCOPE NOTE: unlike Prisma Estonia (prismamarket.ee, a full
grocery storefront), prisma.fi's __NEXT_DATA__.props.pageProps.categories
lists only 13 top-level departments -- Elektroniikka, Kodinkoneet, Kirjat,
Koti, Muoti, Lelut ja lastentarvikkeet, Urheilu ja vapaa-aika, Piha ja
puutarha, Remontointi, Autoilu, Kauneus ja hyvinvointi, Lemmikit,
Ajankohtaista -- with NO food/grocery department. S Group's Finnish
grocery delivery runs through the separate s-kaupat.fi site; prisma.fi is
general merchandise only. Confirmed live 2026-08-06 by enumerating all 13
top-level category ids from the homepage payload. Scaffolded anyway as a
wide non-food retailer_sku source (electronics/home/beauty/pets/books/
sports/garden/renovation/automotive) -- the classifier will assign
non-food COICOP leaves; do not expect any 01.x coverage from this source.

Next.js SSR: every /kategoriat/<id>/<slug>?page=N category page embeds its
own product batch (48/page), `productTotalCount`, and a `subCategories`
list (further /kategoriat/ links to recurse into) directly in
__NEXT_DATA__.props.pageProps -- no client-side fetch needed. Prices are
in minor units (cents); confirmed live against the rendered price text
('4,95 €' for a product whose JSON price=495). Sample: /kategoriat/17/
kauneus-ja-hyvinvointi -> 'Emendo 100ml hierontaöljy rentouttava' 4.95 EUR.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.prisma.fi"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_PAGE_SIZE = 48
MAX_PAGES = 80  # safety cap per category

# Top-level departments, harvested live 2026-08-06 from
# __NEXT_DATA__.props.pageProps.categories on the homepage.
_SEED_CATEGORIES = (
    (3096, "ajankohtaista"),
    (15, "elektroniikka"),
    (11, "kodinkoneet"),
    (1857, "kirjat"),
    (4, "koti"),
    (5, "muoti"),
    (8, "lelut-ja-lastentarvikkeet"),
    (6, "urheilu-ja-vapaa-aika"),
    (14, "piha-ja-puutarha"),
    (3, "remontointi"),
    (89, "autoilu"),
    (17, "kauneus-ja-hyvinvointi"),
    (7, "lemmikit"),
)


def _page_props(response_text):
    m = _NEXT_DATA_RE.search(response_text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data.get("props", {}).get("pageProps", {})


class PrismaFiSpider(scrapy.Spider):
    name = "prisma_fi"
    allowed_domains = ["prisma.fi"]
    currency = "EUR"
    language = "fi"

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

    async def start(self):
        for cat_id, slug in _SEED_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/kategoriat/{cat_id}/{slug}?page=1",
                callback=self.parse_category,
                meta={"cat_id": cat_id, "slug": slug, "page": 1},
            )

    def parse_category(self, response):
        pp = _page_props(response.text)
        if pp is None:
            logger.warning(f"prisma_fi: no __NEXT_DATA__ at {response.url}")
            return

        slug = response.meta["slug"]
        page = response.meta["page"]
        products = pp.get("products") or []
        logger.info(f"prisma_fi: {slug} page={page} products={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            name = p.get("productName")
            sok_id = p.get("sokId")
            price = p.get("finalPrice")
            if not name or sok_id is None or price is None:
                continue
            item_slug = p.get("slug") or str(sok_id)
            yield {
                "product_id": str(sok_id),
                "product_name": html.unescape(name).strip()[:500],
                "category": slug,
                "price": str(price / 100),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/tuotteet/{sok_id}/{item_slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if len(products) >= _PAGE_SIZE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/kategoriat/{response.meta['cat_id']}/{slug}?page={nxt}",
                callback=self.parse_category,
                meta={**response.meta, "page": nxt},
            )

        if page == 1:
            for sub in pp.get("subCategories") or []:
                link = sub.get("link")
                if not link:
                    continue
                sub_m = re.search(r"/kategoriat/(\d+)/([^/?]+)", link)
                if not sub_m:
                    continue
                sub_id, sub_slug = sub_m.group(1), sub_m.group(2)
                yield scrapy.Request(
                    f"{_BASE}/kategoriat/{sub_id}/{sub_slug}?page=1",
                    callback=self.parse_category,
                    meta={"cat_id": sub_id, "slug": sub_slug, "page": 1},
                )
