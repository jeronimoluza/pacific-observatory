"""
Spider for Lidl Poland -- https://www.lidl.pl/.

Same custom Vue SSR storefront platform family as lidl_si/lidl_rs/lidl_gr
(identical numeric category-hub IDs across markets, e.g. h10071012 = fresh
produce, h10071049 = frozen food, h10095761 = dairy). Unlike those three
markets, Poland's category hub pages under-render in plain SSR HTML (e.g.
/h/owoce-i-warzywa/h10071012 server-renders only 1 of what turns out to be
1 total item) -- but each hub page embeds a Nuxt config pointing at the
site's own JSON search/category API used to hydrate the grid:

    GET https://www.lidl.pl/q/api/category/h/<slug>/h<id>
        ?assortment=PL&locale=pl_PL&version=v2.0.0&pageId=<id>
        &offset=<n>&fetchsize=100

This is the enumeration route the batch brief's observed `gridboxes`
endpoint (`/p/api/gridboxes/PL/pl?erpNumbers=...`) is a hydration
shortcut for -- `gridboxes` takes an explicit SKU list and is not itself
enumerable, but this `/q/api/category/...` endpoint returns the *same*
`gridbox.data` product blob (confirmed identical erpNumbers, e.g.
100404480/100400316 from the batch brief's own example both appear under
odziez-damska/h10067567) while natively supporting offset/fetchsize
paging, so no SKU list needs to be sourced separately.

Verified live 2026-09-10:
  - 63 /h/ category hub slugs harvested from the homepage top nav (same
    convention as lidl_si/rs/gr).
  - Enumerability: odziez-damska/h10067567 (numFound=1298) at
    offset=0/100/200 with fetchsize=100 returned 100/100/100 items with
    ZERO pairwise erpNumber overlap -- clean disjoint tiling.
  - offset must be requested in fixed fetchsize-aligned steps (0, 100,
    200, ...); a non-aligned offset (e.g. 999) or a large explicit
    fetchsize at a large offset (e.g. fetchsize=1000 at offset=1000)
    triggered a server-side clamp that silently truncated the page --
    this spider always pages in fixed steps of _FETCH_SIZE to stay clear
    of that.
  - Sum of numFound across all 63 hubs is ~10,224 (some items may be
    cross-listed in more than one hub, so this is an upper bound on
    distinct products, not an exact catalog size).
  - Catalog skews non-food/home-goods (odziez-damska=1298, zabawki-i-gry
    =590, odziez-meska=585, sypialnia=513 vs. mrozonki=4, piekarnia=5,
    sery-nabial-i-jaja=3, owoce-i-warzywa=1) -- same "promo-led catalog"
    (rotating weekly-offer leaflet, not a full grocery assortment) already
    documented for lidl_si/rs/gr.
  - Price lives at flat top-level price.price / price.currencyCode (PLN),
    matching lidl_rs's shape; falls back to regionsPrices.1.currentPrice
    .price for the (rare, per lidl_si/rs precedent) Lidl-Plus-loyalty-only
    items, same as the other three markets.
  - robots.txt disallows `*?offset=*` and `*pageId=*`, but this project
    runs with ROBOTSTXT_OBEY=False repo-wide (price_scraping/settings.py),
    same footing as every other API-pattern spider in this repo.
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lidl.pl"
_API = "https://www.lidl.pl/q/api/category/h/{slug}/h{cid}"
_FETCH_SIZE = 100

# (slug, category-hub id) harvested from the homepage top nav, 2026-09-10.
_CATEGORIES = [
    ("akcesoria-dla-niemowlat-i-dzieci", "10067576"),
    ("akcesoria-i-wyposazenie-warsztatu", "10067534"),
    ("akcesoria-samochodowe", "10067538"),
    ("artykuly-dla-zwierzat", "10067551"),
    ("artykuly-do-domu", "10096287"),
    ("bieganie", "10067547"),
    ("biuro", "10067555"),
    ("budowa-i-remont", "10067536"),
    ("buty-i-akcesoria", "10067569"),
    ("chlodzenie-i-zamrazanie", "10067529"),
    ("dania-gotowe", "10071020"),
    ("dodatki-i-dekoracje", "10067559"),
    ("domki-ogrodowe-i-zadaszenia", "10067540"),
    ("elektronarzedzia", "10067532"),
    ("fitness", "10067543"),
    ("gotowanie-i-pieczenie", "10067523"),
    ("grill-i-akcesoria", "10067525"),
    ("kemping-i-trekking", "10067542"),
    ("kuchnia-i-jadalnia", "10067556"),
    ("kwiaty-rosliny-i-akcesoria-do-roslin", "10067539"),
    ("lazienka", "10067553"),
    ("maszyny-i-akcesoria-do-szycia", "10067530"),
    ("mrozonki", "10071049"),
    ("multimedia-i-technologia", "10067564"),
    ("nakrycie-stolu-i-naczynia", "10067524"),
    ("narzedzia-akumulatorowe-i-akumulatory", "10067531"),
    ("narzedzia-reczne", "10067535"),
    ("odziez-damska", "10067567"),
    ("odziez-dziecieca-2-8-lat", "10067575"),
    ("odziez-dziecieca-9-15-lat", "10067570"),
    ("odziez-meska", "10067568"),
    ("odziez-robocza", "10067537"),
    ("odziez-sportowa", "10067541"),
    ("ogrod-i-balkon", "10067558"),
    ("ogrzewanie-i-chlodzenie", "10067566"),
    ("oswietlenie", "10067561"),
    ("owoce-i-warzywa", "10071012"),
    ("piekarnia", "10096086"),
    ("pokoj-dzienny", "10067554"),
    ("pokoj-niemowlecy-i-dzieciecy", "10067557"),
    ("pranie-i-prasowanie", "10067528"),
    ("przechowywanie-i-organizacja", "10067526"),
    ("przedpokoj-i-magazyn", "10067560"),
    ("rowery-i-akcesoria", "10067544"),
    ("sery-nabial-i-jaja", "10095761"),
    ("slodycze-i-przekaski", "10096205"),
    ("spizarnia", "10096095"),
    ("sporty-wodne", "10067545"),
    ("sporty-zimowe", "10067546"),
    ("sprzatanie-domu", "10067527"),
    ("sprzet-i-narzedzia-ogrodowe", "10067533"),
    ("sprzety-i-akcesoria-kuchenne", "10067522"),
    ("sypialnia", "10067552"),
    ("szkola-i-kreatywnosc", "10067577"),
    ("tekstylia-domowe", "10067565"),
    ("termorobot-mc-smart", "10067521"),
    ("ubranka-dla-niemowlat", "10067574"),
    ("uroda-i-pielegnacja-ciala", "10067563"),
    ("walizki-i-akcesoria-podrozne", "10067572"),
    ("wina-piwa-i-alkohole-mocne", "10096268"),
    ("zabawa-i-sporty-zespolowe", "10067548"),
    ("zabawki-i-gry", "10067573"),
    ("zdrowie-i-dobre-samopoczucie", "10067549"),
]


class LidlPlSpider(scrapy.Spider):
    name = "lidl_pl"
    allowed_domains = ["lidl.pl"]
    currency = "PLN"
    language = "pl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, slug, cid, offset):
        url = (
            f"{_API.format(slug=slug, cid=cid)}"
            f"?assortment=PL&locale=pl_PL&version=v2.0.0&pageId={cid}"
            f"&offset={offset}&fetchsize={_FETCH_SIZE}"
        )
        return scrapy.Request(
            url,
            callback=self.parse,
            meta={"slug": slug, "cid": cid, "offset": offset},
            dont_filter=True,
        )

    async def start(self):
        for slug, cid in _CATEGORIES:
            yield self._request(slug, cid, 0)

    def parse(self, response):
        slug = response.meta["slug"]
        cid = response.meta["cid"]
        offset = response.meta["offset"]
        try:
            payload = response.json()
        except ValueError:
            logger.error("lidl_pl: non-JSON response for %s offset=%s", slug, offset)
            return

        num_found = payload.get("numFound", 0)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n_parsed = 0
        for entry in payload.get("items", []):
            gridbox = entry.get("gridbox") or {}
            data = gridbox.get("data")
            if not isinstance(data, dict):
                continue
            item = self._build(data, scraped_at)
            if item:
                n_parsed += 1
                yield item
        logger.info(
            "lidl_pl: %s offset=%s numFound=%s parsed=%s",
            slug,
            offset,
            num_found,
            n_parsed,
        )

        next_offset = offset + _FETCH_SIZE
        if next_offset < num_found:
            yield self._request(slug, cid, next_offset)

    def _price(self, data: dict):
        # Flat shape (lidl_rs/lidl_pl): price.price / price.currencyCode.
        flat = data.get("price")
        if isinstance(flat, dict) and isinstance(flat.get("price"), (int, float)):
            return flat["price"]
        # Loyalty-only fallback (lidl_si/rs/gr precedent):
        # regionsPrices.1.currentPrice.price or .currentLidlPlusPrice.price.price
        region = (data.get("regionsPrices") or {}).get("1") or {}
        price_block = region.get("currentPrice")
        if isinstance(price_block, dict) and isinstance(
            price_block.get("price"), (int, float)
        ):
            return price_block["price"]
        plus_block = region.get("currentLidlPlusPrice")
        nested = plus_block.get("price") if isinstance(plus_block, dict) else None
        if isinstance(nested, dict) and isinstance(nested.get("price"), (int, float)):
            return nested["price"]
        return None

    def _category(self, data: dict):
        raw = data.get("category") or ""
        parts = [p.strip() for p in raw.split("/") if p.strip()]
        parts = [p for p in parts if p.lower() != "kategorie"]
        return " > ".join(parts) if parts else None

    def _build(self, data: dict, scraped_at: str):
        price = self._price(data)
        if not price:
            return None
        name = data.get("fullTitle") or data.get("title") or ""
        name = html.unescape(str(name)).strip()
        if not name:
            return None
        canonical = data.get("canonicalPath") or ""
        price_block = data.get("price") or {}
        return {
            "product_id": str(data.get("erpNumber") or ""),
            "product_name": name[:500],
            "category": self._category(data),
            "price": str(price),
            "currency": price_block.get("currencyCode") or self.currency,
            "available": bool(data.get("online", True)),
            "url": f"{_BASE}{canonical}" if canonical else None,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
