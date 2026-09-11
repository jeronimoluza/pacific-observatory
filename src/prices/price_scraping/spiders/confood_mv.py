"""
Confood Maldives — confoodmaldives.com, self-described "FMCG | Supplying
| Hotel Supplies | Food and Beverage" wholesale distributor.

The obvious /shop, /product, /products paths are dead ends (all three
just render the homepage) -- the real WooCommerce catalog lives at
/store (classic WooCommerce loop theme, not the newer Store API: the
`/wp-json/wc/store/v1/products` REST route 404s, so this scrapes the
server-rendered HTML loop instead, same pattern as kazemarket_bi).

`/store/?products-per-page=all` returns the whole catalog in one page
(confirmed 142 distinct product ids, no further pagination needed).

Card markup:
    <li class="product ... post-2268 ... product_cat-sauce ...">
      <a href=".../store/product/<slug>/">...
      <h5 class="woocommerce-loop-product__title">Name</h5>
      <span class="price">
        <del>...<span class="woocommerce-Price-amount">MVR 245</span></del>
        <ins>...<span class="woocommerce-Price-amount">MVR 110</span></ins>
      </span>

Sale items carry BOTH a struck-through original price (in <del>) and the
current price (in <ins>) inside the same .price block -- concatenating
all `.woocommerce-Price-amount` text (the naive approach) would glue
both numbers together into one unparseable string. This spider prefers
`.price ins .woocommerce-Price-amount` (current/sale price) and falls
back to `.price > .woocommerce-Price-amount` (direct child only, which
excludes anything nested in <del>) for non-sale items.

Currency read directly off the payload ("MVR" prefix in the price
markup), matching the manifest default.

Page family: listing only (/store?products-per-page=all) — never
visits a PDP.

Verified live 2026-09-11: --max-items 100 run against the all-products
listing produced rows. Sample: "Kaalar Basmati Rice 5kg", "Edinborough
Mayonnaise 3L (Wholesale)" MVR 110.00 (sale price, correctly not
MVR 245.00).
"""

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class ConfoodMvSpider(scrapy.Spider):
    name = "confood_mv"
    allowed_domains = ["confoodmaldives.com"]
    currency = "MVR"
    language = "en"
    start_urls = ["https://confoodmaldives.com/store/?products-per-page=all"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("li.product"):
            post_id = card.attrib.get("class", "")
            m = re.search(r"\bpost-(\d+)\b", post_id)
            pid = m.group(1) if m else None
            name = card.css(".woocommerce-loop-product__title::text").get()
            url = card.css("a.woocommerce-LoopProduct-link::attr(href)").get()
            price_text = "".join(
                card.css(".price ins .woocommerce-Price-amount ::text").getall()
            )
            if not price_text:
                price_text = "".join(
                    card.css(".price > .woocommerce-Price-amount ::text").getall()
                )
            category = self._category(card)
            price = self._price(price_text)
            if not (name and price and pid):
                continue
            yield {
                "product_id": pid,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": "instock" in (card.attrib.get("class") or ""),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _price(raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = re.sub(r"[^0-9.]", "", raw)
        if not cleaned:
            return None
        try:
            return f"{float(cleaned):.2f}"
        except ValueError:
            return None

    @staticmethod
    def _category(card) -> str | None:
        classes = card.attrib.get("class") or ""
        cats = []
        for value in classes.split():
            if value.startswith("product_cat-"):
                cats.append(value.removeprefix("product_cat-").replace("-", " "))
        return " > ".join(cats) or None
