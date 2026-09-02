"""
Spider for Angoremia (Angola) -- https://angoremia.shop/.

React storefront (Vite + a server-rendered "catalogo" shell that shows "A
carregar produtos..." before hydration) backed by an open Supabase
PostgREST API. Neither the bundle's URL literals nor its variable-renamed
minified code reveal the Supabase project or anon key directly -- both
were recovered from a live Playwright network trace of the `/catalogo`
route, which is the "Playwright to discover, plain HTTP to scrape" pattern:
the anon key is Supabase's standard public key (RLS gates access, not key
secrecy), so a plain HTTP GET with it works without ever running a browser
at collection time.

Live-verified 2026-09-01: 10 active rows total (`ativo=eq.true`, PostgREST
`count=exact` -- this is a small, real but thin catalog, not a capped
sample). Prices in `preco` are already whole AOA (no cents, no minor-unit
scaling) -- cross-checked against the rendered PDP for
"LASANHA COM OVO 10*500g": API returns preco=27500, page renders "27 500
Kz".

KNOWN DATA DEFECT ON THE SOURCE SITE (verified, not a scraper bug): 6 of
10 rows carry a `slug`/`categoria_slug` that names a different product
than the current `nome` (e.g. slug="detergente-liquido-2l" but
nome="AZEITONA CAMPONES EM PACOTE 25*100G", categoria_slug="higiene" for
what is clearly a food item by its own description text). Confirmed via
(1) a fresh Supabase LIST re-pull matching byte-for-byte, (2) a per-slug
DETAIL query (the same shape the site's own PDP uses) agreeing with the
list, and (3) live Playwright renders of all 5 non-trivial mismatched PDP
URLs showing the identical name/price/category as scraped -- the site's
own rendered page for detergente-liquido-2l literally displays "Categoria:
higiene" under an olives product. Read as a stale slug+category left over
from a product rename, not fabricated or joined-wrong data -- see the
full verification writeup in configs/.../angoremia_ao.yaml. `category` is
emitted as scraped (faithful to what the site shows) but is unreliable for
roughly half of this source's rows; `product_name` + `price` are not
affected and match the live PDP every time checked.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://gysuaverjqobepozhmnq.supabase.co/rest/v1/produtos"
_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd5c3VhdmVyanFvYmVwb3pobW5xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQxOTk3MTYsImV4cCI6MjA5OTc3NTcxNn0."
    "-xMTOk3qVw1RYhetaZbs-DfXMQR3f_CGzYdMfbaNK_4"
)
_SELECT = "slug,nome,marca,categoria_slug,preco,stock,sku"
_PAGE_SIZE = 200
MAX_PAGES = 10

_WS_RE = re.compile(r"\s+")


class AngoremiaAoSpider(scrapy.Spider):
    name = "angoremia_ao"
    allowed_domains = ["angoremia.shop", "supabase.co"]
    currency = "AOA"
    language = "pt"

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

    def _request(self, offset: int):
        url = (
            f"{_BASE}?select={_SELECT}&ativo=eq.true"
            f"&order=created_at.desc&limit={_PAGE_SIZE}&offset={offset}"
        )
        return scrapy.Request(
            url,
            headers={"apikey": _ANON_KEY, "authorization": f"Bearer {_ANON_KEY}"},
            callback=self.parse_page,
            meta={"offset": offset},
        )

    async def start(self):
        yield self._request(0)

    def parse_page(self, response):
        offset = response.meta["offset"]
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"angoremia_ao: non-JSON response at offset={offset}")
            return
        if not isinstance(products, list) or not products:
            return
        logger.info(f"angoremia_ao offset={offset} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            slug = p.get("slug")
            name = _WS_RE.sub(" ", html.unescape(str(p.get("nome") or ""))).strip()
            if not slug or not name:
                continue
            price = p.get("preco")
            if price is None:
                continue
            yield {
                "product_id": str(p.get("sku") or slug),
                "product_name": name[:500],
                "category": p.get("categoria_slug"),
                "price": str(price),
                "currency": self.currency,
                "available": str(p.get("stock") or "").lower() == "disponivel",
                "url": f"https://angoremia.shop/produto/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if len(products) >= _PAGE_SIZE and (offset // _PAGE_SIZE + 1) < MAX_PAGES:
            yield self._request(offset + _PAGE_SIZE)
