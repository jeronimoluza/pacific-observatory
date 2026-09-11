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
  curl_cffi is a TLS/JA3 fingerprint denylist against that specific
  impersonation signature, not a real content-level proof-of-work for
  these 8 -- so for them, disabling impersonation alone is already
  sufficient and Playwright never needs to run at collection time.
- One tenant, nesraf.com, stayed 403 even to a plain (non-impersonating)
  request. There, and presumably on harder hcdn deployments generally, a
  real headless Chromium homepage visit is required: the browser's own
  `page.goto()` still comes back 403, but the challenge page's embedded
  JS solves the proof-of-work in the background and sets an `hcdn`
  cookie regardless -- carrying that cookie forward on a plain HTTP
  request then returns 200.

Design ("Playwright to clear the challenge once, plain HTTP to scrape",
matching the pattern already used for JSON-API discovery elsewhere in this
repo): run a single Chromium homepage visit per crawl via Playwright's
ASYNC api (Scrapy already runs under TWISTED_REACTOR = AsyncioSelector-
Reactor, so the sync Playwright api cannot be used here -- it refuses to
run inside an existing event loop), harvest whatever cookies that visit
produced, and hand them to WooBaseSpider's ordinary Store API pagination
over plain Twisted HTTP11. Every page of every subsequent crawl run still
starts with a fresh warm-up (spider start-up cost only, not per-request):
cheap relative to a full page load per product page, and robust to a
tenant whose block is content-level rather than a fingerprint denylist.
If a page still comes back 403 mid-crawl (challenge re-armed), the
warm-up is re-run once and that page is retried before giving up on it.

Uses the cached Chromium at ~/.cache/ms-playwright/chromium-1200 on the
box this was built on -- `playwright install` itself fails there (OS is
unsupported by Playwright's installer) but the cached browser launches
fine; nothing here re-invokes the installer.
"""

import logging
from urllib.parse import urlsplit

import scrapy
from playwright.async_api import async_playwright

from ._woo_base import WooBaseSpider

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
                # 403 (nesraf.com) -- wait it out before reading cookies.
                await page.wait_for_timeout(_WARMUP_WAIT_MS)
                cookies = await ctx.cookies()
            finally:
                await browser.close()
        return {c["name"]: c["value"] for c in cookies}

    async def start(self):
        cookies = await self._warm_up()
        logger.info(
            f"{self.name}: warm-up on {self._home_url} collected "
            f"{len(cookies)} cookies"
        )
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            # A JS-challenge tenant (nesraf.com) can still 403 the very
            # first page even after a successful cookie warm-up on a later
            # visit; without handle_httpstatus_list, Scrapy's HttpError-
            # Middleware silently drops 403 responses before parse_page
            # ever sees them, and the 403-retry branch below never fires.
            meta={**self._meta(1), "handle_httpstatus_list": [403]},
            cookies=cookies,
            headers={"User-Agent": _UA},
        )

    async def parse_page(self, response):
        if response.status == 403 and not response.meta.get("rewarmed"):
            page = response.meta["page"]
            logger.warning(
                f"{self.name}: page={page} still 403 -- re-running warm-up once"
            )
            cookies = await self._warm_up()
            yield scrapy.Request(
                self._page_url(page),
                callback=self.parse_page,
                meta={
                    **self._meta(page),
                    "rewarmed": True,
                    "handle_httpstatus_list": [403],
                },
                cookies=cookies,
                headers={"User-Agent": _UA},
                dont_filter=True,
            )
            return
        for result in super().parse_page(response):
            yield result
