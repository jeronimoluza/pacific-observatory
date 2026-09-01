"""Superstan (Afghanistan) -- https://superstan.market/, "Afghanistan online
shopping store" (self-described "Afghanistan's first cryptocurrency
supermarket", offering staple-food and household delivery; also runs
donor-style "Emergency" bundle SKUs alongside plain per-item groceries).

Standard WooCommerce Store API (/wp-json/wc/store/v1/products), but the host
sits behind an "hcdn" bot-wall -- identical signature to dawana_sd (Sudan)
and zaad.delivery: bare curl_cffi with impersonate=chrome124/chrome120/
chrome131/safari17_0 all flat-403 with an identical 6,192-byte "Checking
your browser before accessing..." body, on both the homepage AND the API
path. A real Playwright-driven Chromium navigating straight to the API URL
passes cold (200, real JSON) with no separate challenge-solving step and no
prior homepage visit needed -- confirmed live 2026-09-01. Reuses the
dawana_sd pattern verbatim.

Small catalog: 93 raw listings at per_page=100 (single page, X-WP-Total: 93),
but the catalog is NOT 93 distinct products -- see the dedup section below.
Prices are USD, not AFN, despite delivering inside Afghanistan (contact/
about copy and product set -- rice, oil, flour, lentils, eggs, diapers,
hygiene items -- are Kabul-market staples) -- see rule 8 in the onboarding
brief: this is a real Afghanistan-serving storefront quoting in a foreign
currency, not a US/EU site that merely ships worldwide. currency_minor_unit
is 2 for every observed product (e.g. "Mineral Water 0.5L" raw price "80" ->
USD 0.80), so the standard WooCommerce minor-unit division applies.

GIFTING-PLATFORM VERDICT (rule 8): confirmed live 2026-09-01 via the site's
own About Us and Send Money pages. About Us states outright: "The idea for
Superstan was born when we noticed that there was no online way people
could shop for their families and friends in Afghanistan... so that the
Afghans who live outside of Afghanistan can shop for their families or
loved ones who were left behind" -- plus an explicit crypto-to-cash
remittance service at /send/ ("You send us crypto, the recipient will
collect cash directly from our confidants") and a donation pitch ("fifty
dollars can support a family of six for a month. Food delivery is free
for vulnerable families"). This is a **diaspora gifting / remittance-
adjacent commerce platform**, not an ordinary domestic retail shelf --
prices carry a delivery-and-donation margin (e.g. 0.5L mineral water at
$0.80, ~4x Kabul street price) even though bulk staples (wheat flour 50kg
at $30) price close to market rate. Treat this source's prices as an
upper-bound diaspora-gifting price level, not a domestic shelf price.

TRIPLE-LANGUAGE DEDUP (fixes a shipped defect: v1 emitted all 93 raw rows,
inflating ~29-47 real products into 93 rows of double/triple-counted
items at DIFFERENT, conflicting prices). The catalog carries listings in
three locales, identifiable by permalink path: `/product/` (English, 43
listings), `/fa/product/` (Persian, 33), `/ar/product/` (Arabic, 17).

- English and Persian editions of the SAME physical product share a
  non-blank WooCommerce `sku` (e.g. sku "0010" = "Sugar 5Kg" (en, id 958)
  AND "شکر 5 کیلویی" (fa, id 3985), both priced identically at $4.20) AND
  are linked by a WPML `<link rel=alternate hreflang>` pair on the live
  product page -- 29 such pairs confirmed. These are genuine translation
  pairs: deduped by `sku`, keeping the English row as canonical where an
  English member exists, else the Persian one.
- The 17 Arabic-locale listings all carry a BLANK `sku` (confirmed on
  both the list and single-product API responses) and have ZERO hreflang
  alternates on their live pages (confirmed by fetching the Arabic PDP
  directly and finding no `<link rel=alternate hreflang>` tags at all) --
  WPML does not consider them translations of anything. Spot-checking the
  8 Arabic items whose commodity also appears in the en/fa set: 3 matched
  price exactly (milk powder, red kidney beans, eggs) and 4 conflicted
  outright (sugar $5.00 vs the canonical $4.20; lentils $4.00 vs $5.50;
  rice 10kg $17.00 vs $12.00; tomato paste $3.00 vs $1.50) -- i.e. a
  second, disconnected, partially-stale price list with no reliable join
  key back to the canonical catalog. Rather than fabricate a
  name-translation match (which the 4 conflicts show would sometimes be
  outright wrong) or silently double/triple-count the corpus, the Arabic
  edition is DROPPED IN FULL. 13 more en/fa listings also carry a blank
  sku (standalone items with no translation partner at all, e.g.
  "Mineral Water 0.5 Liter", "Baby Care Package") -- these are kept as-is
  since they have no colliding sku to merge against.
- Net: 93 raw listings -> 47 canonical rows (43 en + 33 fa - 29
  sku-merged pairs = 47; the 17 Arabic listings are excluded entirely,
  not merged and not kept).

Two WordPress-side quirks handled in `_item`:
- Product names are a mix of Arabic, Dari and English; left unnormalized
  beyond entity-decoding -- the classifier consumes the raw name.
- `&#8211;` (en-dash) sometimes ships DOUBLY HTML-entity-escaped: the
  underlying WordPress post title already stores the literal text
  "&#8211;" (not a real en-dash character), and Chromium's `<pre>` JSON
  viewer additionally escapes the leading "&" to "&amp;" when serializing
  the page's HTML source (which is what `response.text` reflects here,
  as opposed to a live page's rendered `innerText`, which auto-resolves
  one layer and can mask this in ad-hoc manual checks). A single
  `html.unescape()` only recovers the first layer ("&amp;#8211;" ->
  "&#8211;"); `_unescape_all()` below loops until a fixed point so both
  layers resolve to the actual "–" character.
"""

import html
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

BASE_URL = "https://superstan.market/wp-json/wc/store/v1/products"
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PER_PAGE = 100
MAX_PAGES = 10
_LOCALE_PRIORITY = {"en": 0, "fa": 1}  # lower wins; "ar" is dropped, never in this map

_PRE_RE = re.compile(r"<pre[^>]*>(.*)</pre>", re.S)


def _unescape_all(s: str, max_passes: int = 4) -> str:
    """Repeatedly html.unescape() until stable (handles double-escaping)."""
    prev = s
    for _ in range(max_passes):
        cur = html.unescape(prev)
        if cur == prev:
            return cur
        prev = cur
    return prev


def _locale_of(permalink: str) -> str:
    if "/fa/product/" in permalink:
        return "fa"
    if "/ar/product/" in permalink:
        return "ar"
    return "en"


class SuperstanAfSpider(scrapy.Spider):
    name = "superstan_af"
    allowed_domains = ["superstan.market"]
    currency = "USD"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    def _page_meta(self, page: int) -> dict:
        return {
            "playwright": True,
            "playwright_context_kwargs": {"user_agent": DESKTOP_UA},
            "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            "playwright_page_methods": [PageMethod("wait_for_timeout", 3000)],
            "page": page,
        }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}?per_page={PER_PAGE}&page=1",
            callback=self.parse_page,
            dont_filter=True,
            meta=self._page_meta(1),
        )

    def parse_page(self, response):
        page = response.meta["page"]
        m = _PRE_RE.search(response.text)
        raw = m.group(1) if m else response.text
        try:
            products = json.loads(raw)
        except ValueError:
            logger.warning("superstan_af: non-JSON response at page=%d", page)
            return
        if not isinstance(products, list) or not products:
            return
        logger.info("superstan_af page=%d raw_count=%d", page, len(products))

        # Drop the unlinked Arabic edition outright -- no sku, no WPML
        # hreflang link back to the canonical en/fa catalog, and confirmed
        # price conflicts where the same commodity exists in both (see
        # module docstring). Group the remaining en/fa listings by sku so
        # translation pairs collapse to one canonical row.
        groups: dict[str, list[dict]] = defaultdict(list)
        dropped_ar = 0
        for p in products:
            locale = _locale_of(p.get("permalink") or "")
            if locale == "ar":
                dropped_ar += 1
                continue
            sku = (p.get("sku") or "").strip()
            key = sku if sku else f"__nosku__{p.get('id')}"
            groups[key].append(p)

        n = 0
        for key, members in groups.items():
            members.sort(
                key=lambda p: _LOCALE_PRIORITY.get(
                    _locale_of(p.get("permalink") or ""), 9
                )
            )
            canonical = members[0]
            item = self._item(canonical)
            if item:
                n += 1
                yield item

        logger.info(
            "superstan_af page=%d canonical_rows=%d dropped_ar=%d raw=%d",
            page,
            n,
            dropped_ar,
            len(products),
        )
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE_URL}?per_page={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                dont_filter=True,
                meta=self._page_meta(nxt),
            )

    def _item(self, p: dict):
        prices = p.get("prices") or {}
        raw_price = prices.get("price")
        if raw_price is None:
            return None
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            value = int(raw_price) / (10**minor) if minor else int(raw_price)
        except (TypeError, ValueError):
            value = raw_price
        if not value:
            return None
        cats = p.get("categories") or []
        cat = (
            " > ".join(
                c.get("name") for c in cats if isinstance(c, dict) and c.get("name")
            )
            or None
        )
        name = _unescape_all(str(p.get("name") or "")).strip()
        name = re.sub(r"\s+", " ", name)
        if not name:
            return None
        permalink = p.get("permalink") or ""
        return {
            "product_id": str(p.get("id") or p.get("sku")),
            "product_name": name[:500],
            "category": cat,
            "price": str(value),
            "currency": prices.get("currency_code") or self.currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": permalink,
            "language": _locale_of(permalink),
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
