"""Choppies eBasket (Botswana) — https://chptst205.echoppies.com/

Choppies is a major regional (Botswana-headquartered) supermarket chain.
This is its online "eBasket" storefront -- note the hostname
(`chptst205.echoppies.com`) looks like a staging alias, but it serves a
real, live, publicly-reachable catalogue with a Botswana Pula currency
icon (`botswana-currency.png`) and genuine food SKUs (TOMATO PP, CARROTS
1 KG PP, WHITE BREAD, CHICKEN TWIN PACK, CHOPPIES 2L FRESH MILK, ...) --
treated as a live source on that evidence, not rejected for the odd
hostname.

Custom/legacy PHP e-commerce platform (jQuery 1.7/1.8, Rackspace CDN
assets) -- NOT Woo/Shopify/PrestaShop/OpenCart/Magento. No WAF: plain
non-impersonating `requests` gets HTTP 200 on every path tested
2026-09-11.

Category discovery: `index.php?cat=<slug>` nav links found on the
`popular.php` landing page -- b_cfc, m_beverages, "m_edible groceries",
"m_ethnic products", m_fresh, "m_general merchandise", "m_house hold",
m_perishable, "m_personal care", m_pets (space-containing slugs are
URL-encoded by the spider). Category taxonomy is food-dominant (fresh,
perishable, edible groceries, beverages) with a couple of non-food
categories mixed in (household, personal care, pets) -- left in scope,
the classifier routes those SKUs correctly on their own product names.

Listing: `index.php?cat=<slug>&page=N`, 20 products/page in
`div.itemBox` blocks: an anchor with `href=".../product_detail.php?pdt=<slug>"`
and `id="productImageWrapID_<pid>"`, followed (same block) by
`h5#productNameWrapID_<pid>` (name) and a price span
`id="productPriceWrapID_<pid>"` (e.g. "25.95", already in Pula units, no
minor-unit division needed). No visible "N of M" total or `<a href=...
page=N>` pagination link in the HTML -- `&page=N` was found to work by
direct guess-and-check rather than by following a link.

Enumerability: CONFIRMED live 2026-09-11 -- `index.php?cat=m_edible
groceries` page1 vs page2 (`&page=2`) returned 20 vs 20 product ids with
ZERO overlap (genuinely different products, not a re-served page). No
published total, so the spider walks pages until an empty page (0 matches)
or MAX_PAGES is hit, per category.

Currency: BWP (Pula) confirmed from the site's own currency icon and price
display convention (no "$"/"R" ambiguity); prices are plain decimal Pula
values, not minor units.

Language: en (product names and category labels are English).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://chptst205.echoppies.com"
CATEGORIES = [
    "b_cfc",
    "m_beverages",
    "m_edible groceries",
    "m_ethnic products",
    "m_fresh",
    "m_general merchandise",
    "m_house hold",
    "m_perishable",
    "m_personal care",
    "m_pets",
]
MAX_PAGES = 30  # safety cap per category (600 SKUs)

_PRODUCT_RE = re.compile(
    r'<div class="itemBox[^"]*">\s*<a title="[^"]*" href="(?P<url>[^"]+)" '
    r'id="productImageWrapID_(?P<pid>\d+)">.*?'
    r'<h5 id="productNameWrapID_\d+">(?P<name>[^<]+)</h5>.*?'
    r'id="productPriceWrapID_\d+">(?P<price>[\d.]+)</span>',
    re.S,
)


class ChoppiesEbasketBwSpider(scrapy.Spider):
    name = "choppies_ebasket_bw"
    allowed_domains = ["chptst205.echoppies.com", "echoppies.com"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"{BASE_URL}/index.php?cat={quote(cat)}&page=1",
                callback=self.parse_category,
                meta={"category": cat, "page": 1},
                dont_filter=True,
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        matches = list(_PRODUCT_RE.finditer(response.text))
        logger.info(
            f"{self.name}: category={category} page={page} count={len(matches)}"
        )
        for m in matches:
            yield {
                "product_id": m.group("pid"),
                "product_name": m.group("name").strip(),
                "category": category.replace("m_", "").replace("b_", "").title(),
                "price": m.group("price"),
                "currency": self.currency,
                "available": True,
                "url": m.group("url"),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if matches and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{BASE_URL}/index.php?cat={quote(category)}&page={next_page}",
                callback=self.parse_category,
                meta={"category": category, "page": next_page},
                dont_filter=True,
            )
