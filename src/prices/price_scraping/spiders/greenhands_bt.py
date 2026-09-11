"""
Spider for Green Hands Bhutan (https://greenhands.bt/) -- "Your Online Farm
Shop", a small Thimphu farm-produce e-grocer.

Custom Laravel/Botble-style storefront (csrf-token meta tag, `/uploads/images`
media path). No JSON API found (Store API / products.json both absent --
this is not WooCommerce/Shopify). Product cards render server-side on
category listing pages under `div.product`.

TLS: requests.get() with the default certifi bundle raises
SSLError/CertificateVerifyError on this host (bad/self-signed intermediate on
greenhands.bt as of 2026-09-11) -- plain curl_cffi impersonate="chrome124"
clears it fine, so Scrapy's default TLS stack (not curl_cffi) is used here;
no impersonation needed, just don't rely on requests+certifi for probing.

Category taxonomy is fixed and tiny -- 3 categories linked from the site nav,
enumerated 2026-09-11 (no sitemap.xml). ALL 91 products across the 3
categories are FOOD (vegetables/fruits, eggs/cereals/dairy,
fresh-cut/dehydrated veg) -- no non-food categories exist on this site.

Pagination: none. `?page=2` on every category returns the SAME 68/9/14 items
as `?page=1` (verified live 2026-09-11) -- the site renders the whole
category on one page. start_urls therefore need no pagination follow-up.

Price: "Nu. 60" inside `p.price span.price-sale`, followed by a unit suffix
text node ("/ Pkt", "/ Kg", "/ bdl", "/ ltr") as a sibling of the price
paragraph inside `div.pricing`. Unit text is folded into product_name via the
category field instead of a separate schema column (schema has no unit
field); category is left as the site's own category slug title instead,
since the unit suffix is short free text, not a taxonomy.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_SLUGS = [
    "vegetables-fruits",
    "eggs-cereals-and-dairy-products",
    "fresh-cut-dehydrated-veges",
]

_CATEGORY_LABELS = {
    "vegetables-fruits": "Vegetables & Fruits",
    "eggs-cereals-and-dairy-products": "Eggs, Cereals & Dairy Products",
    "fresh-cut-dehydrated-veges": "Fresh-cut & Dehydrated Vegetables",
}


class GreenhandsBtSpider(scrapy.Spider):
    name = "greenhands_bt"
    allowed_domains = ["greenhands.bt"]
    currency = "BTN"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    # greenhands.bt's TLS cert fails curl_cffi's default verification; the
    # project-wide RandomBrowserMiddleware already sets meta["impersonate"]
    # on every request, so disabling curl_cffi's verification just means
    # adding impersonate_args (precedent: goto_pk.py, mojsupermarket_me.py).
    _META = {"impersonate_args": {"verify": False}}

    def start_requests(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"https://greenhands.bt/category/{slug}",
                callback=self.parse,
                meta=self._META,
            )

    @staticmethod
    def _parse_price(text: str | None) -> float | None:
        # "Nu. 40" -- strip the currency prefix's own "." FIRST, then pull
        # digits (with optional thousands commas), otherwise the prefix's
        # period is misread as the decimal point (Nu. 40 -> 0.40 bug).
        if not text:
            return None
        m = re.search(r"[\d,]+(?:\.\d+)?", text.replace("Nu.", "").replace("Nu", ""))
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        slug = response.url.rstrip("/").rsplit("/", 1)[-1]
        category = _CATEGORY_LABELS.get(slug, slug)

        cards = response.css("div.product")
        if not cards:
            logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            name_link = card.css("h3 a")
            product_name = (name_link.css("::text").get() or "").strip()
            href = name_link.attrib.get("href")
            if not product_name or not href:
                continue
            url = response.urljoin(href)

            price_text = card.css("div.pricing span.price-sale::text").get()
            price = self._parse_price(price_text)
            if price is None:
                logger.warning(f"Could not extract price for {product_name} on {response.url}")
                continue

            yield {
                "product_id": None,
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"Scraped {len(cards)} product cards from {response.url}")
