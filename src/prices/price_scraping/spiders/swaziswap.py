"""SwaziSwap -- https://swaziswap.com/. Eswatini-domestic online
marketplace ("Proudly Eswatini", delivery within 60km of Mbabane) carrying
listings from local first-party sellers (Second Hand Appliances, Boiler Art
Engineering, plus individual sellers).

Django server-rendered HTML, no WAF, no JS needed -- /catalogue returns the
whole grid to a plain fetch.

Card shape (verified 2026-09-12):
    <div class="product-card">
      <div class="card-img-wrap"><img alt="DEEP FAT FRYER">
        <span class="condition-badge used">2nd Hand</span></div>
      <div class="card-body">
        <p class="card-store">Second Hand Appliances</p>
        <h3 class="card-name">DEEP FAT FRYER</h3>
        <p class="card-price"><span>E </span>400.00</p>
        ... <a href="/product/deep-fat-fryer/" class="btn-details">

ENUMERABILITY, measured 2026-09-12: /catalogue prints its own count in a
`.stats-bar` -- "<strong>8</strong> products" -- and renders exactly 8
`.product-card` blocks with 8 distinct /product/<slug>/ urls. The page
accepts no pagination: /catalogue?page=2 returns a byte-identical response
(same 98,357-byte body, same 8 cards), and every category facet in the
sidebar reads "0 products" except the ones these 8 sit in. So this is a
single complete page, not page 1 of N -- the page1-vs-page2 diff test is
inapplicable the same way it is for busiquip_sz's static bundle. The
spider still reads the stats-bar count and warns when the rendered card
count disagrees with it, which is the tripwire for the day the catalog
outgrows one page.

Catalog mix at onboarding: second-hand appliances (deep fat fryer, bar
fridge), locally fabricated steel goods (braaistand, sliding gate, rabbit
cage, swing set) and used vehicle parts (brake pads, wheels/tyres) -- wide
across COICOP 05 / 07, so coicop_codes is left unset for the classifier.

channel: marketplace -- SwaziSwap is a seller-directory platform, not a
first-party retailer; its product names are seller-authored, which is
exactly what `census.py` excludes from the corpus census. Tagged honestly
rather than as a shop. Its own store directory (/stores) is the higher-value
surface if this source is ever deepened; at 4 stores it is not worth a
second spider today.

Currency SZL: the card prints "E " (Emalangeni), matching countries.yaml's
Eswatini default. Set at class level.

Page family: listing only (the card carries name + price + PDP url; the
spider never fetches /product/<slug>/).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

CATALOGUE_URL = "https://swaziswap.com/catalogue"

_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


class SwaziswapSpider(scrapy.Spider):
    name = "swaziswap"
    allowed_domains = ["swaziswap.com"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(CATALOGUE_URL, callback=self.parse_catalogue)

    def parse_catalogue(self, response):
        declared = response.css(".stats-bar strong::text").get()
        cards = response.css("div.product-card")
        if declared and declared.strip().isdigit():
            if int(declared.strip()) != len(cards):
                self.logger.warning(
                    "stats-bar declares %s products but %d cards rendered -- "
                    "the catalogue may have started paginating",
                    declared.strip(),
                    len(cards),
                )

        seen: set[str] = set()
        for card in cards:
            name = card.css("h3.card-name::text").get()
            href = card.css("a.btn-details::attr(href)").get()
            if not name or not href:
                continue
            name = name.strip()
            url = response.urljoin(href.strip())
            if not name or url in seen:
                continue

            price_text = "".join(card.css("p.card-price ::text").getall())
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

            seen.add(url)
            yield {
                "product_id": url.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name[:500],
                "category": (card.css("p.card-store::text").get() or "").strip() or None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
