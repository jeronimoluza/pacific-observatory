"""Spider for mojSupermarket (Podgorica, Montenegro) -- https://mojsupermarket.me/.

Custom PHP storefront, plain server-rendered HTML, no WAF hit. Category URLs
are `/{slug}-{id}.html` (nested: `/Konzerve+i+tegle-7/Ajvar-51.html`);
product detail URLs are `/proizvod/{slug}-{id}.html`. This walks every
`/{slug}-{id}.html` href reachable from the homepage (excluding `/proizvod/`
links) as a category, recursing into each fetched page for further nested
category links (a shared `seen` set keyed by id prevents re-crawling).

Product cards on a category page are `<li class="product">` containing an
`<a href="/proizvod/...-<id>.html" title="NAME" class="openProduct">` plus a
`<span class="amount">PRICE &euro;</span>`. Montenegro uses the euro
unofficially (no local currency).

Re-verified live 2026-08-06: /Konzerve+i+tegle-7/Ajvar-51.html -> 200, 14
real product cards incl. 'Ajvar domaći blagi 550g - Bakina Tajna' EUR 5.45,
'Ajvar blagi 350g - Podravka' EUR 1.85 -- real Balkan grocery brands
(Podravka, Vipro), not demo-template content (unlike bonella.me, a
WooCommerce install checked and dropped for serving a scrambled
placeholder catalog -- every product priced 0 with an identical unrelated
description).

The site's TLS cert is valid (ZeroSSL, correct hostname) but the server
serves an INCOMPLETE chain -- the issuing intermediate (ZeroSSL RSA DV SSL
CA 2) is missing, so curl_cffi/openssl cannot build a path to the trusted
root and plain verification fails. Fix: vendor that intermediate
(`_mojsupermarket_me_chain.pem`, precedent:
`fetchers/sar/south_asia/bangladesh/_tcb_gov_bd_chain.pem`) and pass a
combined certifi+intermediate bundle via `impersonate_args={"verify": ...}`
on every request -- not `verify=False`.
"""

import html
import logging
import re
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urljoin

import certifi
import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://mojsupermarket.me"
_CHAIN_PEM = Path(__file__).with_name("_mojsupermarket_me_chain.pem")


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "mojsupermarket_me_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


_VERIFY = {"verify": _ca_bundle()}
_CATEGORY_HREF_RE = re.compile(r'href="(/(?!proizvod/)[^"]+?-(\d+)\.html)"')
_CARD_RE = re.compile(
    r'<li class="product">.*?href="(/proizvod/[^"]+?-(\d+)\.html)" title="([^"]+)".*?'
    r'class="amount">([\d,]+)\s*&euro;',
    re.S,
)
MAX_PAGES = 40


class MojsupermarketMeSpider(scrapy.Spider):
    name = "mojsupermarket_me"
    allowed_domains = ["mojsupermarket.me"]
    currency = "EUR"
    language = "sr"

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/",
            callback=self.parse_category,
            meta={"page": 1, "impersonate": "chrome110", "impersonate_args": _VERIFY},
        )

    def _new_category_requests(self, response):
        for path, cat_id in _CATEGORY_HREF_RE.findall(response.text):
            if cat_id in self.seen_categories:
                continue
            self.seen_categories.add(cat_id)
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={
                    "page": 1,
                    "cat_url": urljoin(_BASE, path),
                    "impersonate": "chrome110",
                    "impersonate_args": _VERIFY,
                },
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = response.url.rstrip("/").rsplit("/", 1)[-1].replace(".html", "")
        category = unquote(re.sub(r"-\d+$", "", category).replace("+", " "))
        n = 0
        for _path, product_id, name, price_raw in cards:
            price = price_raw.replace(".", "").replace(",", ".")
            n += 1
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {response.url} page={page} cards={len(cards)} items={n}"
        )

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if cards and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={
                    "page": nxt,
                    "cat_url": cat_url,
                    "impersonate": "chrome110",
                    "impersonate_args": _VERIFY,
                },
            )
