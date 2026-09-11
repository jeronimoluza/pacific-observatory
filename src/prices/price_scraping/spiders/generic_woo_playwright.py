"""
Playwright-fronted sibling of generic_woo_configured, for WooCommerce
storefronts sitting behind an hcdn-style JS interstitial (`server: hcdn`
response header; "Checking your browser before accessing... Just a
moment..." title).

MEASURED 2026-09-11 against the 9 hcdn-flagged tenants named in
~/gapwork/known_blockers_repair_2.md and _repair_1.md:

- curl_cffi impersonation (chrome124/chrome120/safari17_0 -- the repo's
  own IMPERSONATE_BROWSERS profile plus the two fallbacks) 403s on all 9,
  every time. This is the path every plain scrapy.Request in this repo
  takes by default, because scrapy_impersonate.middleware.RandomBrowser-
  Middleware unconditionally stamps request.meta["impersonate"] on every
  request that isn't explicitly opted out -- so generic_woo_configured
  (which never opts out) is guaranteed to 403 here regardless of what a
  human testing with a real browser sees.
- Plain, non-impersonating HTTP (Python `requests`, and by extension
  Scrapy's own default Twisted HTTP11 handler once impersonation is
  disabled) cleared 8 of these 9 tenants immediately, with NO cookie and
  NO Playwright involved at all: leskanso.com, lexmakyty.com,
  gotrustmesl.com, torodocl.com, albasatinaldhabia.com, almatjar.ly,
  greenapplespharmacy.com, souristore.com. The block hcdn presents to
  curl_cffi on these 8 is a TLS/JA3 fingerprint denylist against that
  specific impersonation signature, not a real content-level proof-of-
  work -- so for them, disabling impersonation alone is already
  sufficient and Playwright never needs to touch a Store API request.
- One tenant, nesraf.com, stayed 403 to BOTH curl_cffi AND plain
  (non-impersonating) HTTP, even carrying cookies harvested from a real
  Playwright homepage visit -- Scrapy's Twisted HTTP11 handler's own TLS
  fingerprint is apparently also denylisted there, a stricter posture
  than the other 8. Proven live: keeping ONE Playwright browser page open
  and navigating IT directly to each Store API page (homepage first, then
  the API URLs, all inside the same context/session -- no hand-off to a
  plain-HTTP client at all) returns 200 every time. Handing the harvested
  cookies to a *second*, independent browser context/process (which is
  what scrapy-playwright's own download handler does per request) does
  NOT reproduce this -- it 403s exactly like plain HTTP, confirmed live:
  the cookie-plus-different-client combination is what's rejected, not
  merely the absence of a cookie. So nesraf needs the actual browser
  session kept alive across every page, while the other 8 do not.

Design ("Playwright to clear the challenge once, plain HTTP to scrape" as
the default; escalate to full in-browser rendering only for a tenant that
proves the cheap path does not work): run one Chromium homepage visit per
crawl via Playwright's ASYNC api (Scrapy already runs under
TWISTED_REACTOR = AsyncioSelectorReactor, so the sync Playwright api
cannot be used here -- it refuses to run inside an existing event loop),
harvest whatever cookies that visit produced, and hand them to
WooBaseSpider's ordinary Store API pagination over plain Twisted HTTP11
(curl_cffi impersonation explicitly disabled for this spider -- see
custom_settings -- since it is the thing hcdn blocks). If the very first
page still comes back 403 despite the warm-up cookies, the whole crawl
falls back to a single long-lived Playwright page that never hands off to
plain HTTP: it stays on the homepage-warmed session and navigates that
same page to every Store API URL in turn, extracting each page's JSON
from the rendered body text (Chromium wraps a direct navigation to a JSON
response in a generated HTML/`<pre>` viewer, not the raw bytes).

Uses the cached Chromium at ~/.cache/ms-playwright/chromium-1200 on the
box this was built on -- `playwright install` itself fails there (OS is
unsupported by Playwright's installer) but the cached browser launches
fine; nothing here re-invokes the installer.
"""

import json
import logging
from urllib.parse import urlsplit

import scrapy
from playwright.async_api import async_playwright

from ._woo_base import MAX_PAGES, PER_PAGE, WooBaseSpider

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_WARMUP_WAIT_MS = 8000


class GenericWooPlaywrightSpider(WooBaseSpider):
    name = "generic_woo_playwright"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        # hcdn's block on these tenants IS the curl_cffi TLS/JA3 impersona-
        # tion fingerprint (see module docstring) -- both repo-wide down-
        # loader middlewares that would otherwise touch every request must
        # be off, or RandomBrowserMiddleware re-impersonates every request
        # regardless of what this spider does, and CustomUserAgentMiddle-
        # ware would rotate away from the UA the warm-up cookies were
        # issued to.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "USER_AGENT": _UA,
        # Let a 403 (hcdn still unhappy despite the warm-up cookies) reach
        # parse_page instead of being silently dropped by HttpErrorMiddle-
        # ware -- applies to every page, including the base class's own
        # follow-up pagination requests, not just the first one.
        "HTTPERROR_ALLOWED_CODES": [403],
    }

    def __init__(
        self,
        source_label=None,
        api_url=None,
        base_url=None,
        currency=None,
        language="en",
        category_id=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.BASE_URL = (api_url or base_url or self.BASE_URL or "").rstrip("/")
        self.currency = currency or self.currency
        self.language = language or self.language
        self.CATEGORY_ID = category_id
        parts = urlsplit(base_url or self.BASE_URL)
        self._home_url = f"{parts.scheme}://{parts.netloc}"

    async def _warm_up(self) -> dict:
        """One Chromium homepage visit; returns the cookies it collected."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent=_UA)
                page = await ctx.new_page()
                try:
                    await page.goto(
                        self._home_url, wait_until="domcontentloaded", timeout=30000
                    )
                except Exception as exc:
                    logger.warning(f"{self.name}: warm-up navigation error: {exc}")
                # The challenge's own JS may still be solving the PoW in the
                # background even when the initial navigation itself was a
                # 403 -- wait it out before reading cookies.
                await page.wait_for_timeout(_WARMUP_WAIT_MS)
                cookies = await ctx.cookies()
            finally:
                await browser.close()
        return {c["name"]: c["value"] for c in cookies}

    async def _fallback_playwright_crawl(self):
        """Full in-browser crawl for a tenant where the harvested cookie
        does not survive a hand-off to a different HTTP client. Keeps one
        Playwright page alive from the homepage warm-up through every
        Store API page -- never leaves the browser.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(user_agent=_UA)
                page = await ctx.new_page()
                try:
                    await page.goto(
                        self._home_url, wait_until="domcontentloaded", timeout=30000
                    )
                except Exception as exc:
                    logger.warning(f"{self.name}: fallback warm-up error: {exc}")
                await page.wait_for_timeout(_WARMUP_WAIT_MS)

                pg = 1
                while pg <= MAX_PAGES:
                    url = self._page_url(pg)
                    try:
                        await page.goto(
                            url, wait_until="domcontentloaded", timeout=30000
                        )
                    except Exception as exc:
                        logger.warning(
                            f"{self.name}: fallback nav error at page={pg}: {exc}"
                        )
                        break
                    raw = await page.evaluate("() => document.body.innerText")
                    try:
                        products = json.loads(raw)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"{self.name}: fallback non-JSON body at page={pg} "
                            f"({url})"
                        )
                        break
                    if not isinstance(products, list) or not products:
                        break
                    logger.info(
                        f"{self.name} page={pg} count={len(products)} (fallback)"
                    )
                    for p_ in products:
                        item = self._item(p_)
                        if item:
                            yield item
                    if len(products) < PER_PAGE:
                        break
                    pg += 1
            finally:
                await browser.close()

    async def start(self):
        cookies = await self._warm_up()
        logger.info(
            f"{self.name}: warm-up on {self._home_url} collected "
            f"{len(cookies)} cookies"
        )
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            meta=self._meta(1),
            cookies=cookies,
            headers={"User-Agent": _UA},
        )

    async def parse_page(self, response):
        if response.status == 403:
            logger.warning(
                f"{self.name}: page=1 still 403 over plain HTTP even with "
                "warm-up cookies -- the cheap cookie-then-HTTP shortcut doesn't "
                "work for this tenant; falling back to a single long-lived "
                "Playwright session for the whole crawl"
            )
            async for item in self._fallback_playwright_crawl():
                yield item
            return

        for result in super().parse_page(response):
            yield result
