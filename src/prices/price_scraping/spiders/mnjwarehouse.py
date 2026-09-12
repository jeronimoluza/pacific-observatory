"""M&J Warehouse (Monrovia, Liberia) -- https://mnjwarehouse.com/

Construction materials and plant hire: hollow blocks, paver blocks,
aggregates (sand, crushed rock), and equipment hire day rates. COICOP 04.3
(maintenance and repair of the dwelling) plus plant hire -- a segment none of
Liberia's retail sources reach.

Probed live 2026-09-12 with curl_cffi impersonate=chrome124: a hand-written
static site on Netlify, 4 pages total per its own /sitemap.xml (/, /blocks,
/aggregates, /equipment-hire), every price server-rendered. Each priced line
is an <h3> product heading followed by <p class="price">:

    <h3>4" Hollow Block (Standard Wall Block)</h3>
    <p class="price">$0.85 per block, delivered</p>

CATALOG SIZE recorded deliberately: this is a narrow price list, on the order
of a dozen rows, not a SKU catalog. It clears the >=5-row gate; a future run
seeing ~10 rows should read that as the site's real size.

NOTE for the parse: the same figures also appear in the page's <meta
description> and og:description ("blocks from $0.85 delivered"). This spider
reads only <p class="price"> inside the body, so those marketing repeats never
become rows.

CURRENCY: USD. Bare "$" with no machine-readable code; Liberia is
dual-currency, and Monrovia construction supply quotes US dollars. Judgement
call, recorded not assumed.

Page family parsed: listing (static price pages).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


def _anchor(url: str, name: str) -> str:
    """Give every row on a one-page menu its own URL.

    The repo's DuplicationPipeline drops any item whose `url` it has already
    seen this run (md5 of the url string), so a menu where every dish shares
    the page URL collapses to ONE row -- measured here on 2026-09-12:
    item_scraped_count went to 1 with 14 dishes parsed. Appending a slug of the
    dish name as a fragment is both honest (it is an anchor into that page) and
    the right identity for a menu, where the dish name IS the product key.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{url}#{slug}" if slug else url

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_SITEMAP = "https://mnjwarehouse.com/sitemap.xml"


class MnjwarehouseSpider(scrapy.Spider):
    name = "mnjwarehouse"
    allowed_domains = ["mnjwarehouse.com", "www.mnjwarehouse.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if not u.endswith(".xml")]
        self.logger.info(f"{self.name}: {len(urls)} pages in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_page)

    def parse_page(self, response):
        n = 0
        for node in response.css("p.price"):
            text = " ".join(t.strip() for t in node.css("::text").getall()).strip()
            m = _PRICE_RE.search(text)
            if not m:
                continue
            price = m.group(1).replace(",", "")
            # the product name is the nearest preceding heading
            name = node.xpath(
                "preceding::*[self::h3 or self::h2][1]//text()"
            ).getall()
            name = " ".join(x.strip() for x in name if x.strip())
            if not name:
                continue
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            n += 1
            yield {
                "product_id": None,
                # keep the unit qualifier -- "$0.85 per block, delivered" vs a
                # day rate is the difference between two different goods
                "product_name": f"{name} ({text})"[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": _anchor(response.url, f"{name} {text}"),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        self.logger.info(f"{self.name}: {n} priced rows from {response.url}")
