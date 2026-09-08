"""
Spider for Castorama Poland — https://www.castorama.pl/.

Server-rendered category (.cat) pages carry product cards with clean
`data-testid` attributes -- no Playwright needed. `curl_cffi` chrome124
clears the front page with a plain 200 (no WAF).

Re-verified live 2026-09-06: GET /artykuly-dla-zwierzat.cat -> 200, 1.3MB,
48 unique `[data-testid="product"]` cards, each carrying `data-ean="..."`
(clean product id). `?page=2` on the same category returns a disjoint
48-product set (0 overlap with page 1) -- real pagination, confirmed.
Sample: EAN 5905289867892 'Żelowa mata chłodząca dla zwierząt Aio factory
50x90 cm niebieska 1szt' 36,48 zł.

Price is split across nested spans (whole part / decimal part / "zł" unit,
e.g. `<span data-testid="product-price">36<span>,<!-- -->48<!-- --> <span>zł
</span></span></span>`) -- `::text` on the price node and re-joining is
required; a naive `::text` grab on the outer span only gets "36".

Castorama's catalog is itself a marketplace layer (each card shows
"Sprzedaje i wysyla przedsiebiorca: <seller>" -- third-party sellers
fulfilling under the Castorama storefront), but prices and availability are
real and site-native, not aggregator listings elsewhere -- treated as a
normal retailer_sku source, channel=home-improvement.

Categories below are ~25 leaf `.cat` URLs pulled from the homepage's own
department nav, spanning pets, garden, bathroom, kitchen, tools, painting,
flooring, lighting, cleaning and storage -- not just one department.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.castorama.pl"

_CATEGORIES = [
    "artykuly-dla-zwierzat.cat",
    "dekoracja-scian/lamele-scienne.cat",
    "drewno-i-plyty/plyty-mfp.cat",
    "garderoba-i-przechowywanie/regaly/metalowe-wolnostojace.cat",
    "izolacja/cieplna/welna-mineralna.cat",
    "kuchnia/baterie-kuchenne/baterie-zlewozmywakowe.cat",
    "lazienka/baterie-lazienkowe/wannowe.cat",
    "lazienka/kabiny-prysznicowe-i-akcesoria/kabiny-prysznicowe.cat",
    "lazienka/wc/kompakty-wc.cat",
    "malowanie/farby-wewnetrzne/biale.cat",
    "materialy-budowlane/cegly-bloczki-pustaki/bloczki-betonowe.cat",
    "meble-i-przechowywanie/meble/komody.cat",
    "narzedzia-i-sprzet/elektronarzedzia/wiertarki-wkretarki-i-mloty/wkretarki-akumulatorowe.cat",
    "narzedzia-i-sprzet/narzedzia-reczne/mlotki.cat",
    "ogrod-i-otoczenie/meble-ogrodowe/stoly.cat",
    "ogrod-i-otoczenie/maszyny-ogrodnicze/kosiarki-i-traktorki/kosiarki-spalinowe-z-napedem.cat",
    "ogrzewanie/grzejniki/grzejniki-lazienkowe.cat",
    "okna-drzwi-schody/drzwi-wewnetrzne/drzwi-pokojowe.cat",
    "oswietlenie/oswietlenie-wewnetrzne/kinkiety.cat",
    "plytki-i-podlogi/panele-podlogowe/panele-laminowane.cat",
    "plytki-i-podlogi/plytki-scienne/glazura.cat",
    "sucha-zabudowa/plyty-gipsowe.cat",
    "utrzymanie-porzadku/urzadzenia-i-narzedzia-do-czyszczenia/mopy-i-wiadra.cat",
    "utrzymanie-porzadku/urzadzenia-i-narzedzia-do-czyszczenia/odkurzacze-i-akcesoria/odkurzacze.cat",
    "utrzymanie-porzadku/urzadzenia-i-narzedzia-do-czyszczenia/srodki-czyszczace.cat",
]

_MAX_PAGES_PER_CATEGORY = 3
_PRICE_RE = re.compile(r"[\d,.]+")


class CastoramaPlSpider(scrapy.Spider):
    name = "castorama_pl"
    allowed_domains = ["castorama.pl"]
    currency = "PLN"
    language = "pl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{cat}",
                callback=self.parse_category,
                meta={"cat": cat, "page": 1},
            )

    def parse_category(self, response):
        cat = response.meta["cat"]
        page = response.meta["page"]
        cards = response.css('[data-testid="product"]')
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            item = self._item(card, cat, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"castorama_pl: {cat} page={page} items={n}")

        if cards and page < _MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/{cat}?page={next_page}",
                callback=self.parse_category,
                meta={"cat": cat, "page": next_page},
            )

    def _item(self, card, cat: str, scraped_at: str):
        ean = card.attrib.get("data-ean")
        name = card.css('[data-testid="product-name"]::text').get()
        price_parts = card.css('[data-testid="product-price"] ::text').getall()
        href = card.css('[data-testid="product-link"]::attr(href)').get()
        if not ean or not name or not price_parts:
            return None
        digits = "".join(_PRICE_RE.findall("".join(price_parts)))
        price_str = digits.replace(",", ".").rstrip(".")
        if not price_str:
            return None
        # collapse any stray extra "." from concatenated fragments
        parts = price_str.split(".")
        if len(parts) > 2:
            price_str = parts[0] + "." + "".join(parts[1:])
        try:
            price = float(price_str)
        except ValueError:
            return None
        return {
            "product_id": str(ean),
            "product_name": name.strip()[:500],
            "category": cat.rsplit("/", 1)[-1].replace(".cat", ""),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}{href}" if href else f"{_BASE}/{cat}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
