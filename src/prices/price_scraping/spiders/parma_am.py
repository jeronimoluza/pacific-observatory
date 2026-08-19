"""
Spider for Parma (Armenia) — https://parma.am/en/.

Server-rendered category pages at /en/product/category?slug=<slug>&page=N
(167 category slugs found on the site's own shop nav, spanning baby food,
alcohol, bakery, fresh/cured meat, dairy, produce — a full grocery
taxonomy). Each product card carries name + dram price directly in the
listing HTML: `<a href="/en/product/product?slug=<slug>_<id>"
class="item_name"><span>NAME</span></a> ... <span class="product_price"
data-price="160">160</span>`.

Pagination is NOT self-terminating: requesting a page past the real last
page (confirmed live with page=20/50/200/1000 on the 2-page "bakery"
category) silently clamps to the last page's content instead of returning
empty — so we stop once a page yields no product ids beyond what we've
already seen for that category, not on a short/empty response.

Re-verified live 2026-08-06: category?slug=bakery -> 200, 565KB, real
product 'Croissant "Parma" French, classic 30g' data-price=160 (AMD, ֏).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://parma.am"
_SLUGS = [
    "accessories-for-kids",
    "air-freshener-",
    "alcoholic-beverages",
    "any-rose",
    "baby-food",
    "bakery",
    "basturma-sudjuk",
    "battery",
    "beef",
    "beer",
    "berries",
    "beverages-",
    "birthday-and-events",
    "body-and-skin-care",
    "brandy",
    "bread-and-biscuits",
    "bread-and-pita",
    "breakfast-cereals-flakes",
    "butter-and-margarine",
    "cakes",
    "canned-fish",
    "canned-food",
    "canned-fruits",
    "canned-meat-and-pastes",
    "canned-vegetables",
    "car-air-freshener",
    "cat-food-",
    "cataleya-flowers",
    "caviar",
    "champaign-and-sparkling-wine",
    "cheese",
    "chewing-gum-and-lollipop",
    "chips-and-popcorn",
    "chocolate-collection",
    "chocolate-products",
    "cigar-cigarillo-tobacco",
    "cigarettes",
    "clothes-and-shoes-care",
    "coffee",
    "compote-and-syrup",
    "condensed-milk",
    "cottage-cheese-products",
    "cream",
    "crosswords-magazines-books",
    "deodorants",
    "detergents",
    "diabetic-products",
    "disposable-items",
    "dog-food-",
    "dried-fish",
    "dried-fruits-and-nuts",
    "eggs",
    "fast-food",
    "festive-",
    "fish-and-seafood-",
    "flour",
    "flowers",
    "for-pets-",
    "fresh-and-canned-seafood",
    "fresh-fish",
    "fresh-meat-1",
    "frozen-fish-and-seafood",
    "frozen-products-",
    "fruit-tea",
    "fruits",
    "gift-boxes",
    "gin--absinth-anison",
    "gluten-free",
    "grains",
    "grocery",
    "haberdashery",
    "hair-care",
    "health-and-beauty",
    "honey",
    "hot-chocolate-cocoa-kissel",
    "hot-dishes",
    "household-articles",
    "household-chemicals",
    "household-goods-",
    "ice-and-ice-cream",
    "infant-milk",
    "instant-food",
    "intimate-hygiene-",
    "jelly-and-marshmallow-products",
    "juice-and-beverages-",
    "kefir-and-cocktail",
    "ketchup-mayonnaise-sauce",
    "lamb",
    "lamps-and-candles",
    "latona-flowers",
    "laundry-detergent",
    "legumes",
    "lighter-accessories",
    "liqueur",
    "low-alcohol-beverages-",
    "matsoun",
    "meat-delicacies",
    "meat-products",
    "meat-products-",
    "milk",
    "milk-products-and-eggs-",
    "nail-care",
    "napkins",
    "natural-flowers",
    "natural-juice",
    "office-tools",
    "oil-and-ghee",
    "olives",
    "oral-care",
    "organic-products",
    "other-alcoholic",
    "other-diabetic",
    "other-household-articles",
    "other-household-goods",
    "other-meat",
    "other-stationary",
    "other-sweets",
    "packaging-materials",
    "paper-products",
    "paper-towels",
    "pasta",
    "pastry",
    "pastry-and-crackers",
    "perfumes-and-cosmetics",
    "pig",
    "porridge-cake-puree",
    "poultry",
    "rag-and-gloves",
    "ready-meals",
    "refreshing-beverages",
    "rice",
    "rum",
    "salads-and-appetizers-",
    "sausages",
    "sausages-",
    "seeds-and-sticks",
    "semi-cooked-products",
    "smoke-free-products",
    "smoked-fish",
    "sour-cream",
    "souvenirs",
    "spices",
    "sponge-and-spiral",
    "stationary",
    "sugar-salt-soda",
    "sugar-sugar-substitute",
    "sweets",
    "sweets-desserts",
    "tan-and-okroshka",
    "tea",
    "tea-and-coffee",
    "tequila",
    "toilet-paper",
    "tomato-paste",
    "toys",
    "tropical-fruits",
    "udka",
    "vegetables",
    "vegetables-and-fruits",
    "vegetables-fruits-berries",
    "vermouth",
    "vinegar",
    "water",
    "whiskey",
    "wine",
    "yogurt",
]
_CARD_RE = re.compile(
    r'href="/en/product/product\?slug=([a-zA-Z0-9_-]+)"[^>]*class="item_name"><span>'
    r"([^<]*)</span>.*?data-price=\"([0-9.]+)\"",
    re.S,
)
MAX_PAGES = 40


class ParmaAmSpider(scrapy.Spider):
    name = "parma_am"
    allowed_domains = ["parma.am"]
    currency = "AMD"
    language = "en"

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
        for slug in _SLUGS:
            yield scrapy.Request(
                f"{_BASE}/en/product/category?slug={slug}&page=1",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1, "seen": set()},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        seen: set = response.meta["seen"]

        cards = _CARD_RE.findall(response.text)
        new_ids = {c[0] for c in cards} - seen
        logger.info(
            f"parma_am: {slug} page={page} cards={len(cards)} new={len(new_ids)}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for prod_slug, name, price in cards:
            if prod_slug not in new_ids:
                continue
            yield self._item(prod_slug, name, price, slug, scraped_at)

        if new_ids and page < MAX_PAGES:
            seen = seen | new_ids
            yield scrapy.Request(
                f"{_BASE}/en/product/category?slug={slug}&page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1, "seen": seen},
            )

    def _item(self, prod_slug, name, price, category, scraped_at):
        m = re.search(r"_(\d+)$", prod_slug)
        product_id = m.group(1) if m else prod_slug
        return {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/en/product/product?slug={prod_slug}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
