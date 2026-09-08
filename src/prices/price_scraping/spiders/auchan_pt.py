"""
Spider for Auchan Portugal — https://www.auchan.pt/.

Salesforce Commerce Cloud (SFCC / Demandware) storefront, same family as
continente_pt and pingodoce_pt. Verified live 2026-09-06 with curl_cffi
impersonate="chrome124" (plain requests.get 200s fine, no WAF challenge
observed on this tenant despite cloudflare in front).

Department landing pages (e.g. /pt/alimentacao/) are marketing pages with
no inline products; the actual catalogue lives behind the SFCC
`Search-UpdateGrid?cgid=<id>` AJAX endpoint referenced in the page's
sort-order `<option value=...>` markup. That endpoint is itself plain
server-rendered HTML (confirmed via curl_cffi GET, no JS), so the spider
hits it directly with start/sz pagination per top-level department slug
(used as cgid).

Each product tile carries a `data-gtm='{"name":...,"id":...,"price":...,
"brand":...,"category":...}'` JSON attribute — a complete structured
record, no PDP fetch needed. Sample: 'ATUM POSTA AUCHAN AO NATURAL 120
(84)G' EUR 0.89. Verified page 0 (ids 3877251, 3771753...) and page 24
(ids 3486452, 56832...) return disjoint id sets, confirming real
pagination rather than a fixed teaser.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.auchan.pt"
_GRID_URL = f"{_BASE}/on/demandware.store/Sites-AuchanPT-Site/pt_PT/Search-UpdateGrid"
_PAGE_SIZE = 24
MAX_PAGES = 120  # safety cap per department

_DEPARTMENT_SLUGS = (
    "alimentacao",
    "produtos-frescos",
    "animais",
    "beleza-e-higiene",
    "casa-e-jardim",
    "limpeza-e-cuidados-do-lar",
    "o-mundo-do-bebe",
    "saude-e-bem-estar",
    "eletrodomesticos",
    "tecnologia",
    "papelaria-livraria-e-experiencias",
)

_TILE_RE = re.compile(r'data-urls="({.*?})".*?data-gtm="({.*?})"', re.S)


class AuchanPtSpider(scrapy.Spider):
    name = "auchan_pt"
    allowed_domains = ["auchan.pt"]
    currency = "EUR"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
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
                f"{_GRID_URL}?cgid={slug}&start=0&sz={_PAGE_SIZE}",
                callback=self.parse_grid,
                meta={"slug": slug, "start": 0},
            )

    def parse_grid(self, response):
        slug = response.meta["slug"]
        start = response.meta["start"]
        raw_matches = _TILE_RE.findall(response.text)
        logger.info(f"auchan_pt: {slug} start={start} products={len(raw_matches)}")
        scraped_at = datetime.now(timezone.utc).isoformat()

        for urls_raw, gtm_raw in raw_matches:
            try:
                data = json.loads(html.unescape(gtm_raw))
            except json.JSONDecodeError:
                continue
            name = (data.get("name") or "").strip()
            price = data.get("price")
            product_id = data.get("id")
            if not name or price in (None, "") or not product_id:
                continue
            product_url = f"{_BASE}/pt/"
            try:
                urls = json.loads(html.unescape(urls_raw))
                product_url = urls.get("absoluteProductUrl") or product_url
            except json.JSONDecodeError:
                pass
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": data.get("category", slug),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": product_url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        page = start // _PAGE_SIZE
        if len(raw_matches) >= _PAGE_SIZE and page < MAX_PAGES:
            nxt_start = start + _PAGE_SIZE
            yield scrapy.Request(
                f"{_GRID_URL}?cgid={slug}&start={nxt_start}&sz={_PAGE_SIZE}",
                callback=self.parse_grid,
                meta={"slug": slug, "start": nxt_start},
            )
