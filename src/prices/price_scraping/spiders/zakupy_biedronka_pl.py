"""
Spider for Biedronka home delivery (Poland) — https://zakupy.biedronka.pl.

Salesforce Commerce Cloud (demandware.static asset paths), fully
server-rendered — round 1's TIER_2 label was wrong; a plain-UA curl on a
leaf category returns real prices in the raw HTML (round 1 only checked
the homepage/a wrong guessed slug, both empty-cart placeholders).
Re-verified live 2026-08-06: GET
https://zakupy.biedronka.pl/artykuly-spozywcze/kawy/ -> HTTP 200, 560KB.
Each product tile has a `data-pid="..."` anchor, a `data-title="..."`
attribute on its thumb-link with the product name, and a `N,NN zł` price
string in the surrounding markup. Sample: 'Jacobs Kronung Kawa ziarnista
1 kg' 89,99 zł; 'Lavazza Crema E Gusto Classico Kawa ziarnista palona
1000 g' 99,99 zł. No working ?start=N pagination was found for this theme
(start=24 returned the identical 25 products as start=0), so this walks
one page per leaf category across all 90 leaf category slugs discovered
in the site nav — food (artykuly-spozywcze, nabial, mieso, mrozone,
warzywa, owoce, napoje, piekarnia, dania-gotowe) and non-food
(drogeria, dla-domu, dla-dzieci, dla-zwierzat) alike. Real per-category
counts are much larger than one page (e.g. Artykuły spożywcze 577 SKUs
per shard notes), so this is a partial, not full, per-category catalogue.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "artykuly-spozywcze/do-smazenia-i-wypiekow",
    "artykuly-spozywcze/herbaty",
    "artykuly-spozywcze/kawy",
    "artykuly-spozywcze/produkty-konserwowe",
    "artykuly-spozywcze/produkty-roslinne",
    "artykuly-spozywcze/produkty-sypkie",
    "artykuly-spozywcze/produkty-w-proszku",
    "artykuly-spozywcze/produkty-w-sloikach",
    "artykuly-spozywcze/produkty-z-pomidorow",
    "artykuly-spozywcze/przekaski",
    "artykuly-spozywcze/przyprawy",
    "artykuly-spozywcze/slodycze",
    "artykuly-spozywcze/slone-przekaski",
    "artykuly-spozywcze/sosy",
    "artykuly-spozywcze/sushi",
    "dania-gotowe/dania-mrozone",
    "dania-gotowe/dania-obiadowe",
    "dania-gotowe/surowki-i-salatki",
    "dla-domu/domowy-niezbednik",
    "dla-domu/pranie",
    "dla-domu/sprzatanie",
    "dla-dzieci/chusteczki-nawilzane",
    "dla-dzieci/jedzenie-dla-dzieci",
    "dla-dzieci/pielegnacja-ciala",
    "dla-dzieci/pieluchy",
    "dla-zwierzat/dla-kota",
    "dla-zwierzat/dla-psa",
    "drogeria/dezodoranty",
    "drogeria/golenie-i-depilacja",
    "drogeria/higiena-osobista",
    "drogeria/inne",
    "drogeria/papier-toaletowy-i-chusteczki",
    "drogeria/pielegnacja-ciala-dla-dzieci",
    "drogeria/pielegnacja-ciala",
    "drogeria/pielegnacja-jamy-ustnej",
    "drogeria/pielegnacja-twarzy",
    "drogeria/pielegnacja-wlosow",
    "mieso/bekon",
    "mieso/drob",
    "mieso/kabanosy",
    "mieso/kielbasy",
    "mieso/parowki",
    "mieso/ryby",
    "mieso/salami",
    "mieso/szynki",
    "mieso/wedliny",
    "mieso/wedzonki",
    "mieso/wieprzowina",
    "mieso/wolowina",
    "mrozone/lody",
    "mrozone/mrozone-owoce-morza",
    "mrozone/mrozone-owoce",
    "mrozone/mrozone-ryby",
    "mrozone/mrozone-warzywa",
    "nabial/desery",
    "nabial/jaja",
    "nabial/jogurty-naturalne",
    "nabial/jogurty-owocowe",
    "nabial/jogurty-pitne",
    "nabial/jogurty-vege",
    "nabial/kefiry",
    "nabial/margaryna",
    "nabial/maslanki",
    "nabial/maslo",
    "nabial/mleko",
    "nabial/serki",
    "nabial/sery",
    "nabial/smietana",
    "napoje/bezalkoholowe",
    "napoje/gazowane",
    "napoje/nektary",
    "napoje/niegazowane",
    "napoje/owocowe",
    "napoje/soki",
    "napoje/syropy",
    "napoje/woda",
    "owoce/owoce-swieze",
    "piekarnia/bagietki",
    "piekarnia/bulki",
    "piekarnia/chleb",
    "piekarnia/do-hot-dogow-i-burgerow",
    "piekarnia/pieczywo-tostowe",
    "piekarnia/wypieki",
    "warzywa/grzyby",
    "warzywa/salaty",
    "warzywa/warzywa-swieze",
]

_PID_RE = re.compile(r'data-pid="(\d+)"')
_TITLE_RE = re.compile(r'data-title="([^"]+)"')
_PRICE_RE = re.compile(r"(\d+,\d{2})\s*z[łl]")


class ZakupyBiedronkaPlSpider(scrapy.Spider):
    name = "zakupy_biedronka_pl"
    allowed_domains = ["zakupy.biedronka.pl"]
    currency = "PLN"
    language = "pl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"https://zakupy.biedronka.pl/{slug}/",
                callback=self.parse_page,
                meta={"category": slug},
            )

    def parse_page(self, response):
        body = response.text
        category = response.meta["category"]
        pid_matches = list(_PID_RE.finditer(body))
        seen: set[str] = set()
        blocks = []
        for i, m in enumerate(pid_matches):
            pid = m.group(1)
            if pid in seen:
                continue
            seen.add(pid)
            start = m.start()
            end = (
                pid_matches[i + 1].start() if i + 1 < len(pid_matches) else start + 8000
            )
            blocks.append((pid, body[start:end]))
        for pid, block in blocks:
            item = self._item(pid, block, category)
            if item:
                yield item

    def _item(self, pid: str, block: str, category: str):
        title_m = _TITLE_RE.search(block)
        if not title_m:
            return None
        name = html.unescape(title_m.group(1)).strip()
        price_m = _PRICE_RE.search(block)
        if not name or not price_m:
            return None
        price = price_m.group(1).replace(",", ".")
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"https://zakupy.biedronka.pl/p/{pid}.html",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
