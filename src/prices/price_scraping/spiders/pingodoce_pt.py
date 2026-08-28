"""
Spider for Pingo Doce (Portugal) — https://www.pingodoce.pt/.

The shard's probed URL (mercadao.pt/store/pingo-doce, the Mercadao
white-label platform) now hard 301-redirects unconditionally to
www.pingodoce.pt -- the Mercadao storefront for this retailer appears to
have been retired/merged since the probe. Re-verified live 2026-08-06:
pingodoce.pt itself now runs its own Salesforce Commerce Cloud (SFCC)
catalogue directly (department pages under /home/produtos/<slug>, product
pages under .../<name>-<id>.html) with real prices in the raw homepage
HTML ('7,37 €' etc.), so the spider targets pingodoce.pt in place of the
stale Mercadao URL.

Each department landing page embeds a `Search-UpdateGrid?cgid=<id>` AJAX
URL (SFCC's standard product-grid endpoint); that endpoint is itself
server-rendered HTML (confirmed via a plain GET, no JS), so we extract the
numeric cgid per department once and then page the grid directly with
start/sz. Re-verified: cgid=ec_frutasevegetais_100, sz=100 pagination
walks all 266 products with zero id overlap across pages.

Product cards carry id (`data-bv-product-id`), name+url
(`.product-name-link a`), brand, pack unit, and a clean numeric price
(`<span class="value" content="1.79">`) -- the structured `content`
attribute is used instead of the localized '1,79 €/Kg' text to avoid
locale parsing. Sample: 'Tomate Alongado 57/67' (Nossa Fruta e Legumes)
1.79 EUR.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.pingodoce.pt"
_GRID_URL = (
    f"{_BASE}/on/demandware.store/Sites-pingo-doce-Site/default/Search-UpdateGrid"
)
_PAGE_SIZE = 100
MAX_PAGES = 60  # safety cap per department

_DEPARTMENT_SLUGS = (
    "aguas-sumos-e-refrigerantes",
    "alternativas-alimentares",
    "animais",
    "as-nossas-marcas",
    "bebe-e-crianca",
    "bolachas-cereais-e-guloseimas",
    "cafe-cha-e-achocolatados",
    "casa-e-eletrodomesticos",
    "cervejas-e-sidras",
    "charcutaria-e-queijos",
    "congelados",
    "espirituosas",
    "frutas-e-vegetais",
    "higiene-pessoal-e-beleza",
    "iogurtes-e-sobremesas",
    "leite-e-bebidas-vegetais",
    "limpeza",
    "livraria-e-papelaria",
    "manteiga-margarina-e-natas",
    "mercearia",
    "ovos",
    "padaria-e-pastelaria",
    "parafarmacia",
    "peixaria",
    "talho",
    "vinhos",
)

_CGID_RE = re.compile(r"Search-UpdateGrid\?cgid=([a-zA-Z0-9_]+)")
_CARD_RE = re.compile(
    r'data-bv-product-id="(\d+)".*?'
    r'<div class="product-name-link">\s*<a href="([^"]*)">([^<]*)</a>\s*</div>\s*'
    r'(?:<div class="product-brand-name">\s*([^<]*?)\s*</div>\s*)?'
    r'(?:<div class="product-unit">\s*([^<]*?)\s*</div>\s*)?.*?'
    r'<span class="value" content="([^"]*)"></span>',
    re.S,
)


class PingodocePtSpider(scrapy.Spider):
    name = "pingodoce_pt"
    allowed_domains = ["pingodoce.pt"]
    currency = "EUR"
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

    async def start(self):
        for slug in _DEPARTMENT_SLUGS:
            yield scrapy.Request(
                f"{_BASE}/home/produtos/{slug}",
                callback=self.parse_department,
                meta={"slug": slug},
            )

    def parse_department(self, response):
        m = _CGID_RE.search(response.text)
        if not m:
            logger.warning(f"pingodoce_pt: no cgid found for {response.meta['slug']}")
            return
        cgid = m.group(1)
        yield scrapy.Request(
            f"{_GRID_URL}?cgid={cgid}&start=0&sz={_PAGE_SIZE}",
            callback=self.parse_grid,
            meta={"slug": response.meta["slug"], "cgid": cgid, "start": 0},
        )

    def parse_grid(self, response):
        slug = response.meta["slug"]
        start = response.meta["start"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"pingodoce_pt: {slug} start={start} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, url, name, brand, unit, price in cards:
            display_name = html.unescape(name).strip()
            if brand and brand.strip():
                display_name = f"{html.unescape(brand).strip()} {display_name}"
            yield {
                "product_id": product_id,
                "product_name": display_name[:500],
                "category": slug,
                "price": price.strip(),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        page = start // _PAGE_SIZE
        if len(cards) >= _PAGE_SIZE and page < MAX_PAGES:
            nxt_start = start + _PAGE_SIZE
            yield scrapy.Request(
                f"{_GRID_URL}?cgid={response.meta['cgid']}&start={nxt_start}&sz={_PAGE_SIZE}",
                callback=self.parse_grid,
                meta={**response.meta, "start": nxt_start},
            )
