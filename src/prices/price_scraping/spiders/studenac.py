"""
Spider for Studenac (Croatia) — https://www.studenac.hr/.

studenac.hr is a corporate/informational site (stores locator, loyalty app,
weekly-promo flyer), not a full online supermarket catalogue -- there is no
browsable full-SKU storefront. The catalogue-shaped surface it does expose
is the "Tjedna akcija" (weekly offers) section at /tjedna-akcija: the page
itself renders an empty `<div class="js__productlisting">` client-side
placeholder, but the grid is populated by POSTing the sibling form (action=
/api/products, fields cat/filter/q/p) which returns pre-rendered HTML
product cards -- confirmed live 2026-08-06 via a plain POST (no JS needed).
"More products" pagination uses field `p` (verified against base.min.js:
`$formData.push({name:"p",value:$value})` on the `a[data-page]` "Više
proizvoda" button), and a response's own trailing `data-page="N"` tells us
whether another page exists (absent on the last page).

The sidebar exposes 18 numeric category ids (1-18); we walk each one,
paginating with `p` until a response has no `data-page` marker. This is
the current weekly-offer catalogue only (varies by promo cycle), not
Studenac's full year-round SKU list -- there is no such thing exposed
publicly by this site.

Product cards: `<h3 class="card__title">`, optional `<p class="card__brand">`,
an image at `/uploads/thumbnails/i<n>-<EAN>.jpg` (used as product_id), and
price in `<p class="regular">`. Re-verified live: category 3 (Mliječni
proizvodi i jaja) -> 'Jogurt dukatos' (Dukat) 0,89 €.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://www.studenac.hr/api/products"
_CATEGORIES = {
    1: "Svježe voće i povrće",
    2: "Svježe meso",
    3: "Mliječni proizvodi i jaja",
    4: "Pekarski proizvodi",
    5: "Suhomesnati proizvodi",
    6: "Alkoholna pića",
    7: "Bezalkoholna pića",
    8: "Konzervirani proizvodi i juhe",
    9: "Osnovna prehrana",
    10: "Zdrava prehrana i internacionalna kuhinja",
    11: "Slatkiši i grickalice",
    12: "Kozmetika",
    13: "Čišćenje i pospremanje",
    14: "Kućanske potrepštine",
    15: "Papirnati proizvodi",
    16: "Hrana za kućne ljubimce",
    17: "Sezonski proizvodi",
    18: "Duboko zamrznuti proizvodi",
}
MAX_PAGES = 30  # safety cap per category

_CARD_RE = re.compile(
    r'<h3 class="card__title">([^<]*)</h3>\s*'
    r'(?:<p class="card__brand">([^<]*)</p>)?\s*</div>\s*'
    r'<figure class="card__figure">\s*<img src="https://www\.studenac\.hr/'
    r'uploads/thumbnails/i\d+-(\d+)\.jpg".*?'
    r'<p class="regular">([^<]*)</p>',
    re.S,
)
_HAS_NEXT_RE = re.compile(r'data-page="(\d+)"')


class StudenacSpider(scrapy.Spider):
    name = "studenac"
    allowed_domains = ["studenac.hr"]
    currency = "EUR"
    language = "hr"

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
        for cat_id in _CATEGORIES:
            yield scrapy.FormRequest(
                _API_URL,
                formdata={"cat": str(cat_id), "filter": "", "q": ""},
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"studenac: cat={cat_id} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for name, brand, ean, price in cards:
            display_name = name.strip()
            if brand and brand.strip():
                display_name = f"{brand.strip()} {display_name}"
            yield {
                "product_id": ean,
                "product_name": display_name[:500],
                "category": _CATEGORIES[cat_id],
                "price": price.replace("€", "").replace(",", ".").strip(),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.studenac.hr/tjedna-akcija?p={ean}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if _HAS_NEXT_RE.search(response.text) and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.FormRequest(
                _API_URL,
                formdata={"cat": str(cat_id), "filter": "", "q": "", "p": str(nxt)},
                callback=self.parse_page,
                meta={"cat_id": cat_id, "page": nxt},
            )
