"""
Spider for Electroplanet (Morocco) - https://www.electroplanet.ma/
Electronics / home-appliance retailer (Label'Vie group).

Checked the shared Magento bases in `_magento_base.py` first:
- `MagentoGraphQLBaseSpider` — /graphql is 401'd by an Apache-level
  htpasswd wall (not a Magento auth prompt), site-wide. Dead end.
- `MagentoSSRBaseSpider` — its shared `_PRODUCT_BLOCK_RE` regex assumes a
  flat `<a class="product-item-link">TEXT</a>` anchor. Electroplanet's Luma
  theme nests `<span class="brand">` + `<span class="ref">` inside that
  anchor (the "ref" span is frequently hard-truncated with a literal "...");
  the regex never matches a single card. Bespoke spider instead.

Category tree is 3 levels deep with intermediate "Choisissez une sous
categorie" landing pages (`.family-list-container a`) — only leaf pages
carry `li.product-item` cards. Listing cards carry everything needed
(name, price, id, url) so no PDP visit is required.

Price is read from `[data-price-type="finalPrice"] data-price-amount`, the
raw machine-precise decimal Magento renders regardless of display locale —
this sidesteps the "1 234,56 DH" comma-decimal / non-breaking-space display
text entirely (verified: promo cards render BOTH an `oldPrice` and a
`finalPrice` wrapper, in that order, so selecting by `data-price-type`
rather than positional `[data-price-amount]` is required or a discounted
item's strikethrough price is picked up instead of its sale price).

product_name comes from `img.product-image-photo::attr(alt)`, which carries
the full untruncated name (the anchor's own text is the truncated "ref").

product_id is `data-product-sku` off `.product-item-info` — this matches
the numeric/slug id embedded in the PDP URL (`p<id>-...html`), not the
separate internal `data-product-id` (Magento entity_id) used inside the
price-box markup.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ROOTS = [
    "articles-cuisines",
    "audio-hi-fi",
    "confort-de-la-maison",
    "entretien-de-la-maison",
    "gros-electromenager",
    "informatique",
    "jeux-consoles",
    "petit-electromenager",
    "sante-beaute-bebe",
    "smartphone-tablette-gps",
    "tv-photo-video",
]


class ElectroplanetMaSpider(scrapy.Spider):
    name = "electroplanet_ma"
    allowed_domains = ["electroplanet.ma"]
    currency = "MAD"
    language = "fr"
    BASE_URL = "https://www.electroplanet.ma"
    MAX_PAGES = 100000  # dedup on `seen`: a re-served page yields fresh=0 and stops

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

    async def start(self):
        for slug in _ROOTS:
            yield scrapy.Request(
                f"{self.BASE_URL}/{slug}",
                callback=self.parse,
                meta={"page": 1, "seen": set()},
            )

    def parse(self, response):
        seen = response.meta.get("seen")
        if seen is None:
            seen = set()
        page = response.meta.get("page", 1)

        category = self._breadcrumb(response)
        cards = response.css("li.product-item")
        fresh = 0
        for card in cards:
            item = self._item(card, response, category)
            if item is None:
                continue
            if item["product_id"] in seen:
                continue
            seen.add(item["product_id"])
            fresh += 1
            yield item

        # Recurse into sub-categories only on a branch's first page.
        if page == 1:
            for href in response.css(".family-list-container a::attr(href)").getall():
                yield response.follow(
                    href, callback=self.parse, meta={"page": 1, "seen": set()}
                )

        # Paginate while this page yielded fresh items (a re-served last
        # page stops naturally once `fresh` hits 0).
        if fresh and page < self.MAX_PAGES:
            nxt = page + 1
            base = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base}?p={nxt}",
                callback=self.parse,
                meta={"page": nxt, "seen": seen},
            )

    @staticmethod
    def _breadcrumb(response):
        parts = [
            t.strip()
            for t in response.css(".breadcrumbs .items .item ::text").getall()
            if t.strip()
        ]
        # First crumb is always "Accueil" (Home) — drop it.
        parts = [p for p in parts if p.lower() != "accueil"]
        return " > ".join(parts) if parts else None

    def _item(self, card, response, category):
        info = card.css(".product-item-info")
        product_id = info.attrib.get("data-product-sku")
        name = card.css("img.product-image-photo::attr(alt)").get()
        href = card.css("a.product-item-link::attr(href)").get()
        price_amt = card.css(
            '[data-price-type="finalPrice"]::attr(data-price-amount)'
        ).get()
        if not (product_id and name and href and price_amt):
            return None
        try:
            price = float(price_amt)
        except ValueError:
            return None
        return {
            "product_id": product_id,
            "product_name": name.strip(),
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.urljoin(href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
