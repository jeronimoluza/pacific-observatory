"""
Lagniappe Provisioning (Belize) -- http://www.belizegrocery.com/, canonical
domain https://www.lagniappebelize.com/ (San Pedro, Ambergris Caye).

The sourcing sheet's URL is plain HTTP/no-TLS and redirects (via a `<base
href>` tag, not an HTTP redirect) to the real, HTTPS-capable domain
lagniappebelize.com -- both resolve to the same IP and serve identical
ClickCartPro (Kryptronic) markup. Confirmed live 2026-09-01, not stale:
homepage shows a dynamic order notice ("ALL ORDERS must be placed a minimum
of 3 days prior to your arrival date... pay your order via ZELLE... we are
experiencing extreme shortages on the island") -- this is a real, currently
operating villa/tourist provisioning grocery service on Ambergris Caye, per
the sourcing sheet's note. It sells INTO Belize (San Pedro), so it clears
the locality bar even though its customer base is tourists/villa renters
rather than residents -- same footing as any Belize retailer.

Tier 1A, server-rendered HTML (ClickCartPro / Kryptronic). Category listing
pages at pretty URLs `/Category/<ref>` embed name + per-unit description +
price directly (`div.prodlistname a`, `div.prodlistdesc p`,
`div[id$='--pricedisp'] td.ecom_pricedisp_price`) -- no need to hit
individual product-detail pages. The ~90 leaf category refs are hardcoded
below (scraped once from the homepage nav); they span groceries, meats,
dairy, bakery, produce, and a large wine/spirits/beer section (Wine, Spirits
& Beer) -- specialty/gourmet import range, so channel is `specialty-food`.

Currency: prices are printed explicitly as "USD&nbsp;<amount>" in the raw
HTML (e.g. "USD 15.95" for Ritz Chips, 8.1oz) -- matches the sourcing
sheet's currency column. Recorded as USD, NOT converted to BZD, per the
wave-13 peg trap.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.lagniappebelize.com"

# Leaf category refs scraped from the homepage nav 2026-09-01. Parent
# categories (e.g. "meats", "alcohol", "bev") are kept alongside their
# children -- ClickCartPro shows only items directly assigned to a given
# ref, so parents and leaves are independent listings, not duplicates.
_CATEGORY_REFS = [
    "Cspice",
    "Germ_w",
    "Spice",
    "alcohol",
    "amcadwhisk",
    "aperitifs",
    "argnt_r",
    "argnt_w",
    "austrla_r",
    "austrla_w",
    "bake",
    "bakery",
    "beauty",
    "beef",
    "beer",
    "bev",
    "bourbon",
    "brandy",
    "brkfst",
    "brmix",
    "cheese",
    "chicken",
    "chili_r",
    "chili_w",
    "cnfruit",
    "cnmeat",
    "cnveg",
    "cof",
    "condiments",
    "cordials",
    "dairy",
    "delimeats",
    "dessert",
    "ethnic",
    "france_r",
    "france_w",
    "frfruit",
    "frshbread",
    "frveg",
    "frzfruit",
    "frzveg",
    "gin",
    "gourmet",
    "groceries",
    "herbs",
    "irshwhisk",
    "italy_r",
    "italy_w",
    "juice",
    "meats",
    "mixes",
    "nerz_r",
    "newz_w",
    "oil",
    "paper",
    "pasta",
    "pastry",
    "pate",
    "pizza",
    "pork",
    "port",
    "prepared",
    "produce",
    "rdwine",
    "rdysrve",
    "rosechmp",
    "rum",
    "safr_r",
    "safr_w",
    "sauces",
    "sausage",
    "scotch",
    "seafood",
    "snack",
    "soda",
    "soups",
    "spain_r",
    "spain_w",
    "spec_deli",
    "specialties",
    "spices",
    "tea",
    "tequila",
    "urag_r",
    "urag_w",
    "us_r",
    "us_w",
    "vodka",
    "water",
    "whwine",
]

_PRICE_RE = re.compile(r"([A-Z]{2,3})\s*[\xa0 ]\s*([\d,]+\.\d{2})")


class LagniappeBzSpider(scrapy.Spider):
    name = "lagniappe_bz"
    allowed_domains = ["lagniappebelize.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        for ref in _CATEGORY_REFS:
            yield scrapy.Request(
                f"{_BASE_URL}/Category/{ref}",
                callback=self.parse_category,
                meta={"category": ref},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        soup = BeautifulSoup(response.text, "html.parser")
        count = 0
        for name_div in soup.select("div.prodlistname"):
            a = name_div.find("a", href=True)
            if not a:
                continue
            # The site alternates, per-response, between a query-string
            # product link (?app=ecom&ns=prodshow&ref=<ref>&sid=...) and a
            # pretty-path link (/Item/<ref>) for the identical product --
            # confirmed live 2026-09-01 (ritz chips served both ways across
            # two fetches of the same /Category/snack listing seconds
            # apart). Match either form.
            m = re.search(r"(?:[?&]ref=|/Item/)([^&\"'/]+)", a["href"])
            if not m:
                continue
            ref = m.group(1)
            pricedisp_div = soup.find("div", id=f"{ref}--pricedisp")
            if pricedisp_div is None:
                continue
            price_cell = pricedisp_div.select_one("td.ecom_pricedisp_price")
            if price_cell is None:
                continue
            price_text = price_cell.get_text(" ", strip=True)
            pm = _PRICE_RE.search(price_text)
            if not pm:
                continue
            currency, price = pm.group(1), pm.group(2).replace(",", "")

            name = self._clean_text(a.get_text(" ", strip=True))
            if not name:
                continue
            desc_div = name_div.find_next_sibling("div", class_="prodlistdesc")
            if desc_div is not None:
                desc = self._clean_text(desc_div.get_text(" ", strip=True))
                if desc:
                    name = f"{name} {desc}"

            yield {
                "product_id": ref,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": currency,
                "available": True,
                "url": f"{_BASE_URL}/index.php?app=ecom&ns=prodshow&ref={ref}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            count += 1
        logger.info("lagniappe_bz category=%s items=%s", category, count)

    @staticmethod
    def _clean_text(text: str) -> str:
        prev = None
        while prev != text:
            prev = text
            text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()
