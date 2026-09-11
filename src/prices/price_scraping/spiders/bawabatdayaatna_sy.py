"""
Bawabat Dayaatna (Syria) -- https://bawabatdayaatna.com/
("بوابة ضيعتنا" -- "Our Village's Gateway")

A genuine Syrian online grocery store (custom Laravel storefront, not a
marketplace/seller-hosting platform like the sooqnaa.com/dex.sy stores
sampled during discovery, which turned out to sell books/pants/crafts).
Real international and regional grocery brands confirmed via its own
/brands/<name> pages: Maggi, Nutella, Oreo, Mars, Snickers, Pringles,
Mentos, Rani, Almarai.

CATEGORIES (from the site's own nav, 2026-09-11): 18 categories, 17 of
them food/beverage (Biscuits, canned-dry-goods, cheese, cold-drinks,
dairy-eggs, energy-drinks, foodstuffs, fresh-fruits-vegetables, herbs,
hot-drinks, meat-poultry, milk-dairy, nuts-and-savory-snacks,
spices-seasonings x2, tea-coffee, water-juices) plus one non-food
(cleaning-household, deliberately excluded here).

LISTING MARKUP: no PDP fetch needed -- each category page renders
`<article class="product-card">` blocks with `a.product-name` (text=name,
href=PDP url) and `div.product-price` (text="185.90 ل.س"). Same shape as
shopsefalana_bw (listing-only extraction).

PAGINATION: `?page=N`. MEASURED 2026-09-11: foodstuffs category page 1 vs
page 2 vs page 3 each returned a disjoint 20-product-slug set (page 1
started with "al-ajdad-creamy-basmati-rice", page 3 was a fully different
20). The spider walks each category until a page contributes zero NEW
product slugs (tracked per category), matching the choppies_ebasket_bw
pattern rather than trusting an empty page or a fixed nav max.

CURRENCY: SYP, read directly from the page's own "ل.س" (Syrian Pound)
suffix on every price -- not inferred from TLD.

coicop_classification: classifier, coicop_codes left unset -- catalogue
spans nearly all of COICOP division 01 plus non-alcoholic beverages
(cold/hot/energy drinks, tea/coffee, water/juices).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://bawabatdayaatna.com"

CATEGORIES = [
    "Biscuits",
    "canned-dry-goods",
    "cheese-alagban",
    "cold-drinks-mshrobat-albard",
    "dairy-eggs-alalban-alagban-oalbyd",
    "energy-drinks-mshrobat-altak",
    "foodstuffs-almoad-alghthayy",
    "fresh-fruits-vegetables-khdroat-ofoakh-tazg",
    "herbs-alaaashab",
    "hot-drinks-mshrobat-alsakhn",
    "meat-poultry",
    "milk-dairy-alhlyb-oalalban",
    "nuts-and-savory-snacks-mksrat-omoalh",
    "spices-seasonings-bharat-otoabl",
    "spices-seasonings-bharat-otoabl-1",
    "tea-coffee",
    "water-juices",
    # "cleaning-household" deliberately excluded -- non-food (COICOP 05.6)
]

MAX_PAGES = 60

_CARD_RE = re.compile(
    r'<a href="https://bawabatdayaatna\.com/products/([a-zA-Z0-9\-]+)" class="product-name">\s*'
    r'([^<]+?)\s*</a>.*?'
    r'<div class="product-price">\s*([\d.,]+)\s*ل\.س',
    re.S,
)


class BawabatdayaatnaSySpider(scrapy.Spider):
    name = "bawabatdayaatna_sy"
    allowed_domains = ["bawabatdayaatna.com"]
    currency = "SYP"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
    }

    def start_requests(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"{BASE}/categories/{cat}?page=1",
                callback=self.parse_category,
                meta={"category": cat, "page": 1, "seen": set()},
            )

    def parse_category(self, response):
        cat = response.meta["category"]
        page = response.meta["page"]
        seen = response.meta["seen"]

        matches = _CARD_RE.findall(response.text)
        new_count = 0
        for slug, name, price_str in matches:
            if slug in seen:
                continue
            seen.add(slug)
            try:
                price = float(price_str.replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            new_count += 1
            yield {
                "product_id": slug,
                "product_name": name.strip()[:500],
                "price": f"{price:.2f}",
                "currency": self.currency,
                "category": cat,
                "url": f"{BASE}/products/{slug}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        logger.info(f"bawabatdayaatna_sy {cat} page={page} new={new_count} total_seen={len(seen)}")

        if new_count > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}/categories/{cat}?page={nxt}",
                callback=self.parse_category,
                meta={"category": cat, "page": nxt, "seen": seen},
            )
