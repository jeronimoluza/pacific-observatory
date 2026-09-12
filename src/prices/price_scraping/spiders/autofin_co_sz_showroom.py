"""Eswatini Autofin Investments -- https://autofin.co.sz/showroom/.

Kia franchise dealer in Mbabane (Cnr. Mshengu Road and Siguca Crescent,
Mbabane H100, Eswatini -- the address is printed on every listing card).
WordPress + the "Auto Listings" plugin; the showroom archive is plain
server-rendered HTML, no WAF, no JS. curl_cffi impersonate=chrome124 and a
bare Scrapy fetch both return 200.

Card shape (verified 2026-09-12):
    <li class="col-3 post-579 auto-listing ... auto-listing-579 ...">
      <div class="summary">
        <h3 class="title"><a href="https://autofin.co.sz/showroom/kia-picanto-1-0-start-mt/"
            title="Kia Picanto 1.0 Start MT"> Kia Picanto 1.0 Start MT </a></h3>
        <ul><li class="odomoter">... 23,000 km</li>
            <li class="transmission">... Automatic</li>
            <li class="body">... <a ...>Compact</a></li></ul>
        <span class="price"><span class="price-amount">
            <span class="currency-symbol">E</span>180,000</span> inc VAT</span>

Page family: listing only. The card already carries name + price + PDP url,
so the spider never fetches /showroom/<slug>/.

ENUMERABILITY, measured 2026-09-12: the showroom archive holds FIVE
listings and that is the whole stock -- /showroom/page/2/ returns HTTP 404
(not an empty page), and the plugin renders no pagination element at all.
The filter form's own <select> options corroborate the size: one make
(Kia), one year (2023), three models (Picanto, Sorento, Sportage), three
body types. So the "page 2 must differ from page 1" check does not apply
here the way it does to a paginated catalog -- there is exactly one page
and it is complete. The spider still follows `a.next.page-numbers` when
the plugin emits one, so stock growth paginates without a code change.

coicop_codes ["07.1.1"] (motor cars) rather than the finer .1/.2 split:
the site's own search facets offer New / Used / Certified side by side, and
the five current cards are low-mileage (4,100-23,000 km) "Certified
Vehicle" stock -- genuinely straddling new and second-hand, so the parent
class is the honest code.

Currency SZL: the card prints <span class="currency-symbol">E</span>
(Emalangeni), matching countries.yaml's Eswatini default. Set at class
level, never parsed from the symbol. Price is quoted "inc VAT" -- the
consumer-facing figure, which is what PPP wants.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

START_URL = "https://autofin.co.sz/showroom/"

_ID_RE = re.compile(r"\bpost-(\d+)\b")
_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]{2})?)")


class AutofinCoSzShowroomSpider(scrapy.Spider):
    name = "autofin_co_sz_showroom"
    allowed_domains = ["autofin.co.sz"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    MAX_PAGES = 40

    async def start(self):
        self._seen: set[str] = set()
        yield scrapy.Request(START_URL, callback=self.parse_page, meta={"page": 1})

    def parse_page(self, response):
        page = response.meta["page"]
        cards = response.css("ul.auto-listings-items li.auto-listing")
        for card in cards:
            url = card.css("h3.title a::attr(href)").get()
            name = card.css("h3.title a::text").get()
            if not url or not name:
                continue
            url = response.urljoin(url.strip())
            name = name.strip()
            if not name or url in self._seen:
                continue

            price_text = "".join(card.css("span.price-amount ::text").getall())
            # Strip the currency-symbol span's "E" before reading digits so a
            # stray symbol can never be absorbed into the number.
            price_text = price_text.replace("E", " ")
            m = _PRICE_RE.search(price_text)
            if not m:
                self.logger.warning("No price on card %s", url)
                continue
            price = m.group(1).replace(",", "")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue

            classes = " ".join(card.css("::attr(class)").getall())
            id_m = _ID_RE.search(classes)
            product_id = id_m.group(1) if id_m else url.rstrip("/").rsplit("/", 1)[-1]

            category = card.css("li.body a::text").get()

            self._seen.add(url)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": (category or "").strip() or None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_url = response.css("a.next.page-numbers::attr(href)").get()
        if next_url and page < self.MAX_PAGES:
            yield scrapy.Request(
                response.urljoin(next_url),
                callback=self.parse_page,
                meta={"page": page + 1},
            )
