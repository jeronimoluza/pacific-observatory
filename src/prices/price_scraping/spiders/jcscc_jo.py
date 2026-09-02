"""Jordan Civil Service Consumer Corporation (JCSCC) online shop --
https://www.jcsccshop.gov.jo/. A government-affiliated consumer
cooperative operating physical grocery/hypermarket-style stores across
Jordan (open to civil servants and the public), with a genuine online
catalog and its own price list -- one operator, not a marketplace.

Custom PHP storefront (0 wp-json / wc hits, not WordPress). Category
listing pages paginate via a clean GET query
(`url.php?title=Category&mainCat=<id>&page=<n>&parentIds[]=<id>...`).
Verified live 2026-09-01: page 1 vs page 2 of the same category return
fully disjoint product ids (9 vs 9 cards, 0 overlap), and pages past the
last one return an EMPTY product list (0 cards) rather than re-serving
the last page -- genuine pagination, not the Magento-style infinite-loop
trap (rule 10).

Each product card (`div.index-tabs-product-slider`) carries: the numeric
product id on `a.addProduvtToFavirateList` (lxml lowercases the HTML
attribute `productId` to `productid` on parse), the Arabic product name +
canonical PDP url (`div.index-product-desc a`), and the price text
(`div.product-price h3`, e.g. "10.00 JD").

JOD 3-decimal check done: labneh (لبنة طيبة 4كغم, 4kg tub, product id
91962) is priced "10.00 JD" on-site -- parsed as float 10.00 JOD (2.50
JOD/kg), a plausible dairy unit price; no 1000x/minor-unit scaling
applied or needed -- the site's own price text already IS the JOD amount.
"""

import re
from datetime import datetime, timezone

import scrapy

_BASE = "https://www.jcsccshop.gov.jo"

# (Arabic slug, numeric category id) top-level divisions scraped from the
# site's own homepage nav.
_TOP_CATEGORIES = [
    ("الالبان-والاجبان-والبيض", "65474"),  # Dairy, cheese & eggs
    ("اللحوم-والدواجن-الطازجة", "66584"),  # Fresh meat & poultry
    ("الأطعمة-المجمدة", "65503"),  # Frozen foods
    ("الحلويات-ومستلزماتها", "65870"),  # Sweets & baking supplies
    ("العناية-الشخصية", "66064"),  # Personal care
    ("العناية-المنزلية", "66264"),  # Home care
    ("المخبوزات-والكيك", "68002"),  # Bakery & cake
    ("وفر-اكثر", "68168"),  # "Save more" promos
    ("المشروبات", "66522"),  # Beverages
    ("البقالة", "66705"),  # Groceries
    ("الصوبات", "68573"),  # Heaters (seasonal, non-food)
]

_MAX_PAGES = 60  # defensive cap; observed categories end well under this


def _price_from_text(text):
    if not text:
        return None
    m = re.search(r"([\d.,]+)\s*JD", text)
    if not m:
        return None
    return m.group(1).replace(",", "")


class JcsccJoSpider(scrapy.Spider):
    name = "jcscc_jo"
    allowed_domains = ["jcsccshop.gov.jo"]
    currency = "JOD"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug, cat_id in _TOP_CATEGORIES:
            yield scrapy.Request(
                self._page_url(cat_id, 1),
                callback=self.parse_category,
                cb_kwargs={"slug": slug, "cat_id": cat_id, "page": 1},
            )

    @staticmethod
    def _page_url(cat_id: str, page: int) -> str:
        return (
            f"{_BASE}/url.php?title=Category&mainCat={cat_id}&fromPrice=&"
            f"toPrice=&sortBy=&page={page}&parentIds[]={cat_id}&brandIds[]="
        )

    def parse_category(self, response, slug, cat_id, page):
        cards = response.css("div.index-tabs-product-slider")
        if not cards:
            return

        for card in cards:
            product_id = card.css("a.addProduvtToFavirateList::attr(productid)").get()
            name = card.css("div.index-product-desc a::text").get()
            href = card.css("div.index-product-desc a::attr(href)").get()
            price_text = card.css("div.product-price h3::text").get()
            price = _price_from_text(price_text)
            if not product_id or not name or not href or price is None:
                continue

            yield {
                "product_id": product_id,
                "product_name": re.sub(r"\s+", " ", name).strip(),
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page < _MAX_PAGES:
            yield scrapy.Request(
                self._page_url(cat_id, page + 1),
                callback=self.parse_category,
                cb_kwargs={"slug": slug, "cat_id": cat_id, "page": page + 1},
            )
