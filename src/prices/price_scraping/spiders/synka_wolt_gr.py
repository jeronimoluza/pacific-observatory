"""
SYN.KA (Crete) via the Wolt delivery marketplace.

SYN.KA has no first-party e-commerce catalogue -- its own site
(synka-sm.gr) only takes phone orders or points customers at Wolt/efood
(/orders/ page, verified live 2026-09-06). efood.gr is Cloudflare-walled
(403 "Just a moment..." across all 5 curl_cffi impersonation profiles), so
Wolt is the only reachable online observation of SYN.KA prices. Uses the
shared `_wolt_base.WoltBaseSpider` (same pattern as ab_vassilopoulos_wolt_gr,
carrefour_wolt_ge, sklavenitis_wolt_cy). Venue slug found via web search
(site:wolt.com synka): "Supermarket SYN.KA Livadia | Wolt | Delivery |
Chania" -> en/grc/chania/venue/synka-supermarket. Verified live: 200, 1.6MB
page, `query-state` React-Query blob present.
"""

from price_scraping.spiders._wolt_base import WoltBaseSpider


class SynkaWoltGrSpider(WoltBaseSpider):
    name = "synka_wolt_gr"
    currency = "EUR"
    language = "el"
    VENUE_PATH = "en/grc/chania"
    VENUE_SLUG = "synka-supermarket"
