"""
Cost.U.Less American Samoa (Ottoville Center, Pago Pago) -- confirmed physical
warehouse-club store in the territory via costuless.com/american-samoa (store
info + hours + phone) and the site's own store-locator (rule-8 locality
satisfied; this is NOT a mainland shipper). No e-commerce catalogue exists for
this storefront -- nav is About Us / Store Locator / Flyers only, no shop.* or
order.* subdomain, robots.txt/sitemap.xml carry no product paths.

/american-samoa/flyers embeds 2-3 rotating weekly circulars via a Flipsnack
flipbook viewer (one <iframe src="https://<cdn>/?hash=..."> per flyer, preceded
by an <h2>date range</h2> in the plain server-rendered HTML -- no Playwright
needed for this page). The flyer PAGE IMAGES themselves are not machine
readable, but Flipsnack's backend runs PDF text extraction server-side and
exposes it as a flat `extractedText` string per page inside a short-lived
(~1hr signed) CloudFront JSON at
`https://<asset-cdn>/<account>/collections/<doc-hash>/data.json` -- the
signature is minted client-side on page load, so only a real browser can
obtain a working URL (confirmed live via a Playwright network trace
2026-09-01; plain curl/requests cannot reproduce the signature). This spider
renders each flyer iframe with scrapy-playwright, captures that JSON via a
`playwright_page_event_handlers` response listener, then parses
`extractedText`.

The text layer's reading order does NOT preserve the flyer's visual (often
2-column) layout, so a naive "name then NOW $price" linear regex silently
mispairs items across column breaks (confirmed: a 2-up "Item A / Item B ...
NOW $X NOW $Y" block reads with both names before both prices). This parser
(`extract_items`) only accepts a "NOW $X.XX"-delimited chunk as one valid row
when the cleaned preceding text carries EXACTLY ONE product-quantity marker
(ct./oz./lb/pk/ml/gal/kg/g -- a compound "X/Y" pair like "12 ct./23.4 oz."
counts as ONE marker for one item). Chunks with zero or 2+ markers are
dropped (logged at DEBUG) rather than guessed at.

Verified 2026-09-01 against the 3 flyers live that day (6 pages total): the
produce/meat/furniture circular (heavy per-lb price-tag graphics, badly
scrambled reading order) parses to zero rows and is entirely dropped --
correct, that page's text is not recoverable -- while the two packaged-
grocery brand inserts (General Mills, Kellanova) yielded 17 clean rows
(Nature Valley, Cinnamon Toast Crunch, Old El Paso, Betty Crocker, Pillsbury,
Pringles, Cheez-It, etc.), all cross-checked against the rendered flyer image
by eye. Expect row counts and which flyers survive the filter to vary week to
week as Cost.U.Less rotates circulars -- a near-zero week (all circulars are
produce/meat-style) is a real, expected outcome, not a bug.

Prices are final USD retail ("NOW $X.XX"), no tax-exclusive footnote seen on
any flyer. No stable per-SKU id is printed anywhere in the flyer; product_id
is synthesised from a slug of the cleaned item name (same convention as
konalivr_gn.py). `url` carries a `#<product_id>` fragment per row so
DuplicationPipeline's url-dedup does not collapse multiple rows scraped from
one flyer page (rule 9 -- a single-page/single-URL source needs a synthetic
per-row key or all but one row is silently dropped).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_FLYERS_PAGE = "https://www.costuless.com/american-samoa/flyers"
_IFRAME_RE = re.compile(r'<h2>([^<]*)</h2><iframe src="(https://[^"]+)"')

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ct|oz|lb|pk|ml|gal|kg|g)\.?"
    r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:ct|oz|lb|pk|ml|gal|kg|g)\.?)?",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"NOW\s*\$\s*([\d,]+\.\d{2})")

_HEADER_CUTOFF_RE = re.compile(
    r"^.*?Prices in Effect:[^.]*?\d{4}\s*(?:&\s*)?"
    r"(?:[A-Z][A-Z\s]{3,40}[A-Z]\s+|While Supplies Last\s*)?",
    re.IGNORECASE | re.DOTALL,
)
_PAGE_FOOTER_RE = re.compile(
    r"Am\s+Samoa,?\s*(?:[A-Za-z]+\s+)*?(?:Insert,?\s*)?P\d+\b\.?", re.IGNORECASE
)
_BOILERPLATE_RES = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"located in ottoville center",
        r"follow us on social media",
        r"never a membership fee!?",
        r"american express",
        r"www\.costuless\.com",
        r"facebook\.com/costulessamericansamoa",
        r"@costuless\.americansamoa",
        r"all items limited to stock on hand\.?",
        r"no rain checks\.?",
        r"we reserve the right to limit quantities\.?",
        r"see store for current store hours:?",
        r"see website for current store hours:?",
        r"see store for more details\.?",
        r"1 purchase = 1 meal",
        (
            r"for every general mills brand product purchased from this ad, "
            r"a meal will be donated to a local food bank in need\.?"
        ),
        r"buy any of these products and you could win\s*\*?",
        r"receive one raffle entry.*?ends\.?",
        r"contest period is[^.]*?\.",
        r"all prizes given in the form of[^.]*?\.",
        r"\d(?:st|nd|rd|th)?\s*p\s*l\s*a\s*c\s*e\s*\$\d+",
        r"off new!?",
    ]
]
# Some inserts repeat a private-label tagline ("Oh so Fresh. Oh so
# Delicious. ... Oh so GOOD!") several times before the real product text;
# collapse all-but-the-last repeat so the shipped name keeps only the one
# that actually belongs to the product ("Oh so GOOD! <product>, <qty>").
_REPEATED_TAGLINE_RE = re.compile(
    r"(?:Oh so [A-Za-z]+!?\.?\s+){2,}(?=Oh so)", re.IGNORECASE
)

# Promo-banner tokens ("SAVE $2", "2 OFF", "WOW!", "CLUB PACK", bare digits/
# "$" left over from a price-tag graphic, etc.) that can appear on either
# side of the real product text within one "NOW $X.XX"-delimited chunk.
_JUNK_TOKEN = (
    r"\$\s*\d+(?:\.\d+)?\s*OFF|"
    r"\d+(?:\.\d+)?\s*OFF|"
    r"\$\d+OFF|"
    r"OFF|"
    r"SAVE\s*\$?\s*[\d.]+¢?|"
    r"SAVINGS?|"
    r"WOW!|"
    r"CLUB PACK|"
    r"PICK|"
    r"NEW!|"
    r"SMOOTH|"
    r"PROTEIN|"
    r"ea\.|"
    r"&|"
    r"\$|"
    r"\d+"
)
_LEADING_JUNK_RE = re.compile(r"^(?:\s*(?:" + _JUNK_TOKEN + r")\s*)+", re.IGNORECASE)
_TRAILING_JUNK_RE = re.compile(r"(?:\s*(?:" + _JUNK_TOKEN + r")\s*)+$", re.IGNORECASE)


def _clean_chunk(chunk: str) -> str:
    chunk = _HEADER_CUTOFF_RE.sub("", chunk)
    chunk = _PAGE_FOOTER_RE.sub(" ", chunk)
    for rx in _BOILERPLATE_RES:
        chunk = rx.sub(" ", chunk)
    chunk = _REPEATED_TAGLINE_RE.sub("", chunk)
    for _ in range(6):
        new = _LEADING_JUNK_RE.sub("", chunk.strip())
        if new == chunk:
            break
        chunk = new
    for _ in range(6):
        new = _TRAILING_JUNK_RE.sub("", chunk.strip())
        if new == chunk:
            break
        chunk = new
    chunk = re.sub(r"\s+", " ", chunk)
    return chunk.strip(" .,-")


def extract_items(text: str) -> list[tuple[str, float]]:
    """Return [(item_name, price), ...] for unambiguous chunks only.

    A chunk (the text between one "NOW $X.XX" token and the previous one) is
    kept only when it reduces, after boilerplate stripping, to exactly one
    product-quantity marker -- i.e. exactly one item's description. Ambiguous
    (0 or 2+ marker) chunks are dropped rather than guessed at, because the
    Flipsnack text layer does not preserve the flyer's 2D layout.
    """
    prices = list(_PRICE_RE.finditer(text))
    rows: list[tuple[str, float]] = []
    start = 0
    for m in prices:
        raw_chunk = text[start : m.start()]
        start = m.end()
        chunk = _clean_chunk(raw_chunk)
        price = float(m.group(1).replace(",", ""))
        if len(chunk) < 5:
            logger.debug("costuless_flyer_as: drop (too short) $%.2f %r", price, chunk)
            continue
        markers = list(_UNIT_RE.finditer(chunk))
        if len(markers) != 1:
            logger.debug(
                "costuless_flyer_as: drop (%d markers) $%.2f %r",
                len(markers),
                price,
                chunk,
            )
            continue
        if not (chunk[0].isalpha() and chunk[0].isupper()):
            # Junk-stripping didn't fully clear the name (leftover digits,
            # "$", stray punctuation) -- drop rather than ship a garbled
            # product_name (rule 5).
            logger.debug(
                "costuless_flyer_as: drop (no clean leading word) $%.2f %r",
                price,
                chunk,
            )
            continue
        rows.append((chunk, price))
    return rows


class CostulessFlyerAsSpider(scrapy.Spider):
    name = "costuless_flyer_as"
    allowed_domains = ["costuless.com", "cloudfront.net", "flipsnack.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_FLYERS_PAGE, callback=self.parse_flyer_list)

    def parse_flyer_list(self, response):
        matches = _IFRAME_RE.findall(response.text)
        logger.info("costuless_flyer_as: %d flyer iframes found", len(matches))
        for title, iframe_url in matches:
            capture: dict = {}
            yield scrapy.Request(
                iframe_url,
                callback=self.parse_flyer,
                errback=self.errback_flyer,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_event_handlers": {
                        "response": self._make_response_handler(capture)
                    },
                    "capture": capture,
                    "flyer_title": title.strip(),
                },
                dont_filter=True,
            )

    @staticmethod
    def _make_response_handler(capture: dict):
        async def _handler(response):
            if "data.json" in response.url:
                try:
                    capture["data"] = await response.json()
                except Exception as exc:  # noqa: BLE001
                    capture["error"] = str(exc)

        return _handler

    async def parse_flyer(self, response):
        page = response.meta["playwright_page"]
        capture = response.meta["capture"]
        title = response.meta["flyer_title"]
        try:
            for _ in range(20):
                if "data" in capture or "error" in capture:
                    break
                await page.wait_for_timeout(500)
        finally:
            await page.close()

        data = capture.get("data")
        if not data:
            logger.warning(
                "costuless_flyer_as: no data.json captured for flyer %r (%s)",
                title,
                capture.get("error"),
            )
            return

        pages = data.get("pages") or {}
        order = pages.get("order") or []
        pdata = pages.get("data") or {}
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for page_id in order:
            text = (pdata.get(page_id) or {}).get("extractedText") or ""
            if not text:
                continue
            for name, price in extract_items(text):
                product_id = f"costuless_as-{_slugify(name)}"
                yield {
                    "product_id": product_id,
                    "product_name": name,
                    "category": None,
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
                n += 1
        logger.info(
            "costuless_flyer_as: flyer %r pages=%d rows=%d", title, len(order), n
        )

    async def errback_flyer(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page is not None:
            await page.close()
        logger.warning("costuless_flyer_as: request failed: %s", failure)
