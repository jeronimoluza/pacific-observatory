"""
Spider for taw9eel.com -- "Taw9eel", a Kuwait online grocery/general-
merchandise storefront (legacy Magento 1, not the modern Luma theme, so
`_magento_base.py`'s markers don't match).

IMPORTANT -- this is NOT a pure first-party catalog. A live sample (175
random PDPs, see below) showed 20% of rows carry an explicit
"- delivered by <Named Partner>" suffix on the product name for a
DIFFERENT business than Taw9eel itself: "The Pharmacy" (12.6% of the
sample -- vitamins, skincare, medicines), plus one-off partners (Union
Trading, Al Nasser, Thouqi, Petzone, Al Rifai For Nuts, Smart Food,
Pharmazone) and pure digital gift cards/subscriptions fulfilled "by
Whatsapp & Email" (Xbox credit, IQIYI, game currency -- not physical
retail at all). Those are third-party marketplace listings under
onboarding rule 14 ("a marketplace can be onboarded as its individual
first-party merchants rather than as one blended aggregate") and this
spider DROPS them rather than mislabel the blended whole as first-party
`hypermarket`. Rows with no delivery-partner suffix, or with
"- delivered by Taw9eel Fast" (Taw9eel's own quick-commerce/dark-store
arm -- confirmed first-party: groceries, frozen meat, produce, dairy,
snacks, cleaning, baby care, all delivered under Taw9eel's own name with
no other business named), are kept and the boilerplate suffix is
stripped from `product_name` per the onboarding brief's rule 5. A few
rows carry a double tag ("Delivered By Pharmazone - delivered by Taw9eel
Fast") -- Taw9eel Fast here is only the logistics leg for a
third-party-sourced item, so the presence of ANY non-Taw9eel-Fast partner
name anywhere in the title drops the row regardless of the Taw9eel Fast
tag alongside it.

Measured on the 175-row live sample: 140/175 (80%) survive the
first-party filter; of those, ~54-56% are food-and-beverage by product
name (groceries, frozen meat/poultry, dairy, produce, snacks, condiments,
coffee/tea, baby formula, pet food) against a remainder of household/
personal-care/baby-gear/beauty/general-merchandise -- a genuine
cross-selling mixed catalog, hence `channel: hypermarket` (matching the
lulu_kw precedent for the same catalog shape), not `supermarket`.

Front page and every product page return HTTP 202 with an AWS WAF
`x-amzn-waf-action: challenge` JS-challenge stub to plain `curl_cffi`
impersonation (chrome124/chrome120/safari17_0 all 202) -- this is the
content-level proof-of-work class the onboarding skill calls out
separately from a TLS fingerprint block; no `curl_cffi` profile clears it.
A real headless Chromium (Playwright) *does* clear it and is issued an
`aws-waf-token` cookie; replaying that cookie with a plain `requests`/
Scrapy session (no Playwright, no TLS impersonation) then gets 200 on
every subsequent page -- confirmed live 2026-09-01 across a homepage
fetch, a PDP fetch, and a category listing fetch, all reusing the same
cookie. This is the "Playwright to discover, plain HTTP to scrape"
pattern: Playwright runs exactly once per crawl, in `start()`, to mint the
token; every PDP request after that is a bare `scrapy.Request` carrying
the captured cookie jar.

Catalog discovery: robots.txt -> Sitemap: sitemap_en/sitemap_index.xml ->
sitemap_products.xml + sitemap_products_1.xml + sitemap_products_2.xml,
63,593 distinct PDP URLs total (25000 + 25000 + 13593) -- a real
multi-shard catalog, not a homepage carousel, and matches the storefront's
own "80,000 products" marketing claim in the right order of magnitude.

PDP extraction (verified against dumped HTML, not guessed):
- product_id: `<meta property="product:retailer_item_id" content="...">`
  -- stable Magento entity id, matches the URL's own numeric suffix.
- product_name: `<h1>` page title. Deliberately NOT `og:title`, which
  carries "Buy " / " - delivered by <store>" boilerplate on every sampled
  PDP (rule: strip retailer boilerplate before it reaches the classifier).
- price: `#product-price-<id> .price` -- Magento's "current effective
  price" span. When a product is discounted this id holds the special
  price (confirmed: Al Safi Milk 4x1L had `old-price-60375`=KD1.88 and
  `product-price-60375`=KD1.56 -- the id WITHOUT `old-` prefix is always
  the one actually charged); when not discounted it's the only price span
  for that id. Prefix "KD" is stripped; no unit-scaling needed (plain
  decimal, not integer minor units).
- KWD 3-decimal check (done explicitly per the onboarding brief): sampled
  25 random PDPs' `product:price:amount` meta plus this site's own
  rendered `.price` spans -- EVERY sampled value terminates in `.XY0` or
  `.XY00` (e.g. "27.5600", never "27.563"). This site itself only prices
  to 2 decimals (10-fils steps); there is no hidden third digit being
  truncated by this spider -- the source data has none to lose.
- category: last non-"Home" breadcrumb crumb (schema.org BreadcrumbList).
- currency: hardcoded "KWD" (dataLayer/meta both confirm KWD; never
  inferred from a display symbol).
- available: a product with no `#product-price-<id>` span (out of stock /
  delisted) is skipped rather than emitted with a null/zero price.
"""

import html
import logging
import random
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HOME = "https://www.taw9eel.com/"
_SITEMAPS = [
    "https://www.taw9eel.com/sitemap_en/sitemap_products.xml",
    "https://www.taw9eel.com/sitemap_en/sitemap_products_1.xml",
    "https://www.taw9eel.com/sitemap_en/sitemap_products_2.xml",
]
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_ITEM_ID_RE = re.compile(r'product:retailer_item_id"\s+content="(\d+)"')
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_BREADCRUMB_RE = re.compile(r'<span property="name">([^<]+)</span>', re.DOTALL)

# Product titles append delivery-partner attribution as one or more
# " - <segment>" tails, e.g. "... - delivered by The Pharmacy - within 2
# Hours" or "... - Delivered By Pharmazone - delivered by Taw9eel Fast".
# Only "Taw9eel Fast" (Taw9eel's own quick-commerce arm) is first-party;
# any OTHER named partner anywhere in the title means the row is a
# third-party marketplace listing and gets dropped entirely (see module
# docstring). Segments that don't match "delivered by ..." at all (plain
# descriptive text) are kept in the cleaned name.
_PARTNER_SEGMENT_RE = re.compile(
    r"^\s*delivered\s+by\s+(.+?)(?:\s+within\b.*)?\s*$", re.IGNORECASE
)
_FIRST_PARTY_PARTNER = "taw9eel fast"


def _clean_name_and_check_first_party(raw_name: str):
    """Split the title on ' - ', drop any 'delivered by <partner>'
    segment while checking whether every such partner is Taw9eel's own
    'Taw9eel Fast' arm. Returns (clean_name, is_first_party)."""
    base_parts = []
    is_first_party = True
    for part in (p.strip() for p in raw_name.split(" - ")):
        m = _PARTNER_SEGMENT_RE.match(part)
        if m:
            partner = re.sub(r"[^a-z0-9 ]", "", m.group(1).strip().lower()).strip()
            if partner != _FIRST_PARTY_PARTNER:
                is_first_party = False
        elif part:
            base_parts.append(part)
    return " - ".join(base_parts).strip(), is_first_party


class Taw9eelKwSpider(scrapy.Spider):
    name = "taw9eel_kw"
    allowed_domains = ["taw9eel.com"]
    currency = "KWD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": _DESKTOP_UA,
    }

    async def start(self):
        cookies, sitemap_texts = await self._bootstrap()
        if not cookies.get("aws-waf-token"):
            logger.warning(
                "taw9eel_kw: no aws-waf-token minted -- WAF challenge not solved,"
                " subsequent requests will likely 202"
            )
        self._cookies = cookies

        # All 3 product-sitemap shards are fetched up front (not one
        # scrapy.Request per shard) and combined into a single shuffled
        # URL list before any PDP request is enqueued. Scrapy's scheduler
        # is LIFO: enqueuing shard-1 -> shard-2 -> shard-3 as separate
        # requests means a --max-items-capped run drains ONLY the
        # last-enqueued shard (confirmed live: an early cut at max-items=30
        # landed entirely inside sitemap_products_2.xml's "Taw9eel Fast"
        # sub-brand tail -- household/electronics, zero food, exactly the
        # non-representative-tail failure mode the onboarding brief warns
        # about). Shuffling the combined list first makes any prefix of it
        # -- capped or full -- an unbiased sample of the whole catalog.
        urls = []
        for text in sitemap_texts:
            urls.extend(_LOC_RE.findall(text))
        urls = list(dict.fromkeys(urls))  # de-dup, preserve nothing meaningful
        random.Random(20260901).shuffle(urls)
        logger.info(f"taw9eel_kw: {len(urls)} distinct product URLs after shuffle")
        for url in urls:
            yield scrapy.Request(
                url,
                cookies=self._cookies,
                callback=self.parse_pdp,
                dont_filter=True,
            )

    async def _bootstrap(self):
        """Run a real headless Chromium once to clear the AWS WAF JS
        challenge, harvest the resulting cookie jar (chiefly
        `aws-waf-token`), and reuse that same authenticated context to
        pull all 3 product-sitemap shards -- avoiding a second, separate
        WAF-solve for the sitemap host. Uses playwright's async API so it
        runs inside Scrapy's own asyncio reactor loop rather than
        spinning a second, conflicting event loop (the sync API forbids
        that)."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=_DESKTOP_UA)
                await page.goto(_HOME, timeout=30000, wait_until="networkidle")
                await page.wait_for_timeout(4000)
                cookies = await page.context.cookies()
                sitemap_texts = []
                for sitemap_url in _SITEMAPS:
                    resp = await page.context.request.get(sitemap_url, timeout=30000)
                    sitemap_texts.append(await resp.text())
            finally:
                await browser.close()
        cookie_jar = {
            c["name"]: c["value"] for c in cookies if "taw9eel" in c["domain"]
        }
        return cookie_jar, sitemap_texts

    def parse_pdp(self, response):
        if response.status != 200:
            logger.warning(f"taw9eel_kw: status={response.status} at {response.url}")
            return
        body = response.text
        id_m = _ITEM_ID_RE.search(body)
        if not id_m:
            return
        product_id = id_m.group(1)

        price_m = re.search(
            rf'id="product-price-{product_id}"[^>]*>\s*<span class="price">\s*KD\s*([0-9.,]+)',
            body,
        )
        if not price_m:
            return
        try:
            price = float(price_m.group(1).replace(",", ""))
        except ValueError:
            return
        if price <= 0:
            return

        h1_m = _H1_RE.search(body)
        if not h1_m:
            return
        raw_name = html.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1))).strip()
        if not raw_name:
            return
        name, is_first_party = _clean_name_and_check_first_party(raw_name)
        if not is_first_party or not name:
            # Third-party marketplace listing (a named delivery partner
            # other than Taw9eel's own "Taw9eel Fast" arm) -- see module
            # docstring. Not this source's inventory to claim.
            return

        crumbs = [html.unescape(c).strip() for c in _BREADCRUMB_RE.findall(body)]
        crumbs = [c for c in crumbs if c and c.lower() != "home"]
        category = crumbs[-1] if crumbs else None

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
