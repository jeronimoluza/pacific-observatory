"""
Pisiffik (Greenland) — https://www.pisiffik.gl/.

Greenland's FIRST price source of any kind (the country had zero manifests
before this pass). Pisiffik is Greenland's largest privately-owned retail
company (~40 stores across the six largest towns) and runs the only real
e-commerce catalogue in the territory.

NOT a food source, and that is expected. Pisiffik's supermarket business is
offline; what it sells online is its department-store side — the Elgiganten
(electronics), Jysk (furniture) and Thansen (auto) franchises, plus
appliances, toys and homeware. A prior sweep found exactly this and skipped
the site for being non-food. It is onboarded here because non-food coverage
is wanted too: a country with one non-food source beats a country with none,
and Greenland's remaining chains (Brugseni, Pilersuisoq) are brochure-only
with no webshop at all.

PrestaShop 1.7, Tier 1A — server-rendered, no anti-bot, no JS needed.
Category pages carry `article.product-miniature` cards with full schema.org
microdata, so prices come from a machine-readable attribute rather than
parsed display text:

    [itemprop="price"]::attr(content)          -> "5249.25"
    [itemprop="priceCurrency"]::attr(content)  -> "DKK"
    [itemprop="sku"]::attr(content)            -> "635743"

Using the `content` attribute sidesteps the Danish display format
("5.249,25 kr." — period thousands separator, comma decimal), which a naive
digit-strip would turn into 524925.

    >>> CRAWL POLICY — DO NOT RAISE THE RATE <<<
    pisiffik.gl publishes an unusually explicit robots.txt. It blocks a long
    list of named AI-training and SEO crawlers outright (GPTBot, ClaudeBot,
    anthropic-ai, Claude-Web, CCBot, PerplexityBot, AhrefsBot, ...) with the
    stated rationale "no SEO benefit, high resource cost", and separately
    throttles Bingbot for "169 hits in one window". The generic
    `User-agent: *` group does NOT disallow category or product pages, but it
    sets `Crawl-delay: 5`.

    This spider therefore pins DOWNLOAD_DELAY = 5.0 and one concurrent
    request, overriding the repo defaults (0.1s / 2 concurrent), and avoids
    every Disallow-ed query pattern (?q=, ?name=, ?search_query=, ?orderby=,
    ?orderway=, ?tag=, ?id_currency=, ?back=, ?n=, ?show=price_drop). A full
    pass is slow by design. The operator has made its load concerns explicit;
    respect them.

Category discovery walks the homepage's `/da/<id>-<slug>` links. Pagination
uses `?page=N`, which is not among the Disallow-ed patterns.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pisiffik.gl"
START_URL = f"{BASE_URL}/da/"
_CATEGORY_RE = re.compile(r"^/da/(\d+)-[^/?#]+$")

# Explicitly Disallow-ed in robots.txt for User-agent: * — never request these.
_BLOCKED_CATEGORY_IDS = {"445", "1132"}

# Safety net only -- the real terminator is the site's own `has_next` link,
# which was verified to disappear exactly when a category runs out of real
# products. This must stay well above the deepest category or it silently
# truncates: at 250 it cut "Dyreartikler" (which runs to ~page 275) at exactly
# 2,250 rows = 250 pages x 9 products. See the manifest for the full autopsy.
MAX_PAGES_PER_CATEGORY = 1000


class PisiffikGlSpider(scrapy.Spider):
    name = "pisiffik_gl"
    allowed_domains = ["pisiffik.gl", "www.pisiffik.gl"]
    currency = "DKK"
    language = "da"

    custom_settings = {
        # robots.txt for User-agent: * sets Crawl-delay: 5. Honoured here.
        "DOWNLOAD_DELAY": 5.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": False,
        "AUTOTHROTTLE_ENABLED": False,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            START_URL,
            callback=self.parse_home,
            errback=self.errback,
            dont_filter=True,
        )

    def parse_home(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            url = urljoin(BASE_URL, href)
            if not url.startswith(BASE_URL):
                continue
            path = url[len(BASE_URL) :].split("?")[0].split("#")[0]
            match = _CATEGORY_RE.match(path)
            if not match:
                continue
            cid = match.group(1)
            if cid in _BLOCKED_CATEGORY_IDS or cid in seen:
                continue
            seen.add(cid)
            # Request the CLEANED path, never `url`. The home page links some
            # categories with a query already attached (e.g.
            # /da/101-skaenke-og-vitriner?page=2). `path` strips it for the
            # regex match, but passing the raw `url` on meant
            # _category_request appended a SECOND query -- producing
            # `?page=2?page=3`, which the server answers by serving page 2
            # forever. has_next therefore never cleared and the category
            # paginated to the cap, burning ~560 requests on duplicates.
            yield self._category_request(f"{BASE_URL}{path}", 1)
        logger.info(f"{self.name}: discovered {len(seen)} categories")

    def _category_request(self, url, page):
        target = url if page == 1 else f"{url}?page={page}"
        return scrapy.Request(
            target,
            callback=self.parse_category,
            errback=self.errback,
            meta={"cat_url": url, "page": page},
            dont_filter=True,
        )

    def parse_category(self, response):
        url = response.meta["cat_url"]
        page = response.meta["page"]
        cards = response.css("article.product-miniature")
        breadcrumb = " > ".join(
            t.strip()
            for t in response.css(
                ".breadcrumb a span::text, .breadcrumb li a::text"
            ).getall()
            if t.strip()
        )
        found = 0

        for card in cards:
            name = (
                card.css('[itemprop="name"] a::text').get()
                or card.css(".product-title a::text").get()
                or ""
            ).strip()
            price = card.css('[itemprop="price"]::attr(content)').get()
            currency = card.css('[itemprop="priceCurrency"]::attr(content)').get()
            sku = card.css('[itemprop="sku"]::attr(content)').get()
            pid = card.attrib.get("data-id-product")
            link = card.css('[itemprop="name"] a::attr(href)').get() or ""
            if not name or not price or not pid:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            found += 1
            yield {
                "product_id": sku or pid,
                "product_name": name[:500],
                "category": breadcrumb,
                "price": price,
                "currency": currency or self.currency,
                "available": True,
                "url": urljoin(BASE_URL, link) or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {url.rsplit('/', 1)[-1]} page={page} "
            f"cards={len(cards)} yielded={found}"
        )

        # Follow pagination only while the page is full-width; an empty or
        # short page ends the category.
        #
        # NOTE: `cards` is NOT a usable end-of-category signal on this site.
        # Every category page carries a fixed 8-product recommendation rail
        # rendered as article.product-miniature, so len(cards) never reaches
        # zero -- a rail-only page past the true end still reports 8. That
        # rail is also the entire source of the run's duplicate drops
        # (~8 x pages). `has_next` IS reliable: verified present on every page
        # carrying real products and absent on the first that carries none.
        # Termination therefore depends on has_next, with the page cap as a
        # backstop that must never be the thing that fires.
        if cards and page < MAX_PAGES_PER_CATEGORY:
            has_next = response.css(
                'a.next::attr(href), .pagination a[rel="next"]::attr(href)'
            ).get()
            if has_next:
                yield self._category_request(url, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
