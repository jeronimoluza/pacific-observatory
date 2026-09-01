"""
Semsem Market (Yemen) — https://smsm.market/.

Custom Laravel multi-vendor marketplace (same script family as souqmy_ye,
yemenbox and the rejected yemenstorez/bab-almandab candidates), but this
deployment is genuinely populated — unlike those three, which had 9-30 SKUs
site-wide and an empty food category. Sana'a-based ("اليمن - صنعاء - شارع حدة"),
single unified "Semsem" branding/checkout; a "become a vendor" CTA exists
(/vendors, /vendor/auth/*) but no distinct third-party seller names were
observed on any product card or PDP, so this is treated as one retailer's
catalog rather than a blended multi-seller marketplace.

The site sells far more than groceries (stationery, toys, phones/tablets,
electronics, fashion, beauty, home/furniture, pharmacy) — this spider is
deliberately SCOPED to the top-level "السوبر ماركت" (Supermarket) department
only, category id=82, via the server-rendered listing route:

    GET /products?id=82&data_from=category&page=<N>

id=82 aggregates its full subtree (مواد غذائية / rice+pasta / oil+ghee /
sugar / grains+legumes / snacks / honey+dates / nuts / spices / juices+
beverages+soft drinks+water) — confirmed by cross-referencing subcategory
ids against the homepage nav. Because the crawl only ever requests id=82,
every row this source emits is a grocery/beverage SKU, which is why it is
tagged `channel: supermarket` rather than `marketplace` even though the
parent site is wider. See the YAML notes for the full reasoning — flag this
for review if a reader disagrees.

Each listing page is server-rendered HTML with 20 product cards
(div.product-single-hover), each carrying name, href, YER price, and a
numeric product_id on the quick-view button (data-product-id). Pagination
verified to genuinely advance (page 1 vs 2 vs 32 all distinct; page 33 has
1 remaining item; page 34 returns zero cards) — walked until a page yields
zero cards rather than a hardcoded page count.

NAME TRUNCATION FIX: the listing card's own markup hard-truncates long
Arabic names with a literal "..." (measured 403/641 = 62.9%). Checked, in
order: (1) no `title=`/`alt=` attribute on the card's anchor or image
carries the full text (`alt=""` is empty on every card observed); (2) the
PDP's `<title>` tag DOES carry the full, untruncated name — verified against
6 sampled truncated products, all matched cleanly with no site-name suffix
or other contamination; (3) never needed to check embedded JSON since (2)
worked. So this spider does a second-pass PDP fetch, but ONLY for items
whose listing-card name ends in "..." (403 of 641, not all 641) — pulls the
`<title>` tag verbatim as the corrected product_name. Non-truncated items
are yielded straight from the listing page with no extra request.

Currency: site shows a single YER price with no old/new-rial switcher found
(unlike souqmy_ye and bab-almandab, which do expose one). Given the Sana'a
address, this is presumed to be the "old" Sana'a/north rial — see the YAML
notes for the USD cross-check performed to sanity-test that inference.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://smsm.market"
CATEGORY_ID = 82  # "السوبر ماركت" (Supermarket) — the only department walked
CATEGORY_LABEL = "السوبر ماركت"
MAX_PAGES = 60  # safety cap; catalog measured at 33 pages / ~641 SKUs
_DIGITS_RE = re.compile(r"[^\d.]")
_TITLE_RE = re.compile(r"<title>([^<]*)</title>")


class SmsmYeSpider(scrapy.Spider):
    name = "smsm_ye"
    allowed_domains = ["smsm.market"]
    currency = "YER"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        return scrapy.Request(
            f"{BASE_URL}/products?id={CATEGORY_ID}&data_from=category&page={page}",
            callback=self.parse_listing,
            errback=self.errback,
            meta={"page": page},
            dont_filter=True,
        )

    def parse_listing(self, response):
        page = response.meta["page"]
        cards = response.css("div.product-single-hover")
        found = 0

        for card in cards:
            name = (card.css("div.single-product-details a::text").get() or "").strip()
            href = card.css("div.single-product-details a::attr(href)").get() or ""
            price_text = (
                card.css(".product-price .text-accent::text").get()
                or card.css(".product-price span::text").get()
                or ""
            ).strip()
            pid = card.css("a.action-product-quick-view::attr(data-product-id)").get()

            if not name or not href or not price_text or not pid:
                continue

            price_parts = price_text.split()
            price = _DIGITS_RE.sub("", price_parts[-1]) if price_parts else ""
            if not price or float(price) <= 0:
                continue

            found += 1
            item = {
                "product_id": pid,
                "product_name": name[:500],
                "category": CATEGORY_LABEL,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

            if name.endswith("..."):
                # Truncated on the listing card — the PDP <title> carries
                # the full name (verified; no title=/alt= fallback exists
                # on the card itself). Fetch it and patch product_name.
                yield scrapy.Request(
                    item["url"],
                    callback=self.parse_pdp_name,
                    errback=self.errback,
                    meta={"item": item},
                    dont_filter=True,
                    priority=1,
                )
            else:
                yield item

        logger.info(f"{self.name}: page={page} cards={len(cards)} yielded={found}")

        if found and page < MAX_PAGES:
            yield self._page_request(page + 1)

    def parse_pdp_name(self, response):
        item = response.meta["item"]
        match = _TITLE_RE.search(response.text)
        full_name = match.group(1).strip() if match else ""
        if full_name:
            item["product_name"] = full_name[:500]
        else:
            logger.warning(
                f"{self.name}: no <title> found on PDP {response.url}, keeping truncated name"
            )
        yield item

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
