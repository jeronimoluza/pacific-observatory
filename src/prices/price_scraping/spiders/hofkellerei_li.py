"""Hofkellerei des Fuersten von Liechtenstein — https://www.hofkellerei.li/.

The Princely House of Liechtenstein's own winery/estate shop, headquartered
in Vaduz, LIECHTENSTEIN (the same estate publishes a "Pinot Noir AOC
Vaduz" bottle -- an actual Vaduz-appellation wine). Genuinely domestic;
the shop listing page itself states free shipping "innerhalb der Schweiz
und Liechtenstein" (within Switzerland AND Liechtenstein), confirming
explicit LI delivery -- no locality ambiguity, unlike the Coop/Migros
question. The estate also farms vineyards in Austria (hofkellerei.at is a
sister site) and this single LI-hosted webshop sells both -- honestly
noted, not hidden.

Custom "XSite" CMS, plain server-rendered HTML (curl_cffi/requests both
return 200, no JS needed). The full catalog (29 products: 2026-09-01,
confirmed via the page's own `document.xf_loadmore...={"limit":99,
"total":29,...}` counter -- 29 is the WHOLE catalog, not a truncated
first page) renders in one request at /de/online-shop.html: no
pagination or per-product-page crawl needed. Each product card carries a
stable numeric id (`div.shop-product-counter[data-id]`), name (`h6`), and
price (`.xs-shop-dynamic-price-toggle`, format "CHF 19,00" -- German
decimal COMMA, converted to a period before float()). Mix of wine
(majority), grape juice, olive oil, honey, and a couple of non-food gift
items (voucher, jewellery box) -- left to the classifier rather than
narrow-scoped, since the catalog is genuinely mixed COICOP.
"""

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"CHF\s*([\d.]+),(\d{2})")


class HofkellereiLiSpider(scrapy.Spider):
    name = "hofkellerei_li"
    allowed_domains = ["hofkellerei.li"]
    start_urls = ["https://www.hofkellerei.li/de/online-shop.html"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        ts = datetime.now(timezone.utc).isoformat()
        for wrapper in response.css("div.xf_loadmore_item"):
            link = wrapper.css('a[href*="/online-shop/detail/"]::attr(href)').get()
            name = wrapper.css("h6::text").get()
            price_text = wrapper.css(".xs-shop-dynamic-price-toggle::text").get()
            product_id = wrapper.css(".shop-product-counter::attr(data-id)").get()
            if not (link and name and price_text and product_id):
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = f"{m.group(1)}.{m.group(2)}"
            category = None
            vol_text = wrapper.css(".wein-detail p").xpath("string()").get()
            if vol_text and "//" in vol_text:
                # Only a real "<volume> // <price>" line carries a usable
                # category; some non-wine items (gift voucher, jewellery
                # box) render just the bare price with no "//" separator --
                # leave category null for those rather than shipping the
                # price string as a fake category.
                category = vol_text.split("//")[0].strip() or None
            yield {
                "product_id": product_id.strip(),
                "product_name": name.strip(),
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(link),
                "language": self.language,
                "scraped_at_utc": ts,
            }
