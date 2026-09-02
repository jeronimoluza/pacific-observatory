"""
Access Haiti — https://accesshaiti.com/ (AirFiber home internet plans).

Real Haiti ISP (Petion-Ville HQ, +509-2812-6000, WhatsApp order links to
+509-3912-6000) offering fiber/fixed-wireless home internet, mobile 4G LTE
and TV. The site itself is a pure client-rendered React SPA
(`<div id="root"></div>`, no server HTML) with NO backing pricing API --
grepping the bundle finds zero `/api` calls. Plan cards are instead
hardcoded directly as JSX string literals inside the built JS bundle
(`/assets/index-<hash>.js`), so this spider fetches that static asset (not
the HTML page) and regexes the plan name / price / headline speed straight
out of the bundle text -- no Playwright needed, the bundle already has the
literal marketing copy that the SPA would otherwise render client-side.

Currency: prices are literal "$XX.XX" in the bundle text with no ISO code
anywhere on the site -- this is a USD-priced Haiti storefront (common for
Haiti fiber/fixed-wireless ISPs), NOT HTG. Emitted as USD, not converted.

8 AirFiber plans confirmed live 2026-09-01 (Basic $54.54 through tier 6
$350.00), each with a distinct headline speed (DL/UL Mbps). Only the home
internet ("AirFiber") plan family is scraped; mobile/TV plan sections
were not found as matching JSX blocks in this bundle and are not chased
further this round.

The bundle filename is content-hashed by the build tool (Vite) and WILL
change on the next deploy -- `start_requests` re-resolves it from the
current homepage's <script src=...> tag on every run rather than hardcoding
the asset URL, so the spider doesn't silently start failing after Access
Haiti's next release.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://accesshaiti.com"
_SCRIPT_SRC_RE = re.compile(r'<script[^>]+src="(/assets/[^"]+\.js)"')
_PLAN_RE = re.compile(
    r'n\.jsx\("h3",\{className:"text-2xl font-bold mb-2",children:"([^"]+)"\}\).*?'
    r'children:"(\$[\d.,]+)"\}\).*?'
    r'children:"•\s*([^"]+)"',
    re.DOTALL,
)


class AccesshaitiHtSpider(scrapy.Spider):
    name = "accesshaiti_ht"
    allowed_domains = ["accesshaiti.com"]
    currency = "USD"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_BASE_URL + "/", callback=self.parse_homepage)

    def parse_homepage(self, response):
        m = _SCRIPT_SRC_RE.search(response.text)
        if not m:
            logger.warning("accesshaiti_ht: no bundle <script src> found on homepage")
            return
        yield scrapy.Request(_BASE_URL + m.group(1), callback=self.parse_bundle)

    def parse_bundle(self, response):
        count = 0
        for name, price, speed in _PLAN_RE.findall(response.text):
            slug = name.lower().replace(" ", "-")
            yield {
                "product_id": f"airfiber-{slug}",
                "product_name": f"{name} ({speed})",
                "category": "Home Internet",
                "price": price.lstrip("$").replace(",", ""),
                "currency": self.currency,
                "available": True,
                # DuplicationPipeline dedups on item['url']; every plan shares
                # response.url (the JS bundle), so append a slug fragment.
                "url": f"{response.url}#{slug}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            count += 1
        logger.info(f"accesshaiti_ht: emitted {count} plan rows from {response.url}")
