"""
Savers Supermarket (Portsmouth, Dominica) -- a supermarket storefront on the
CaribeEats delivery platform
(backend.caribeeats.com/api/business/savers-supermarket-).

Discovered 2026-09-05 by enumerating CaribeEats' *portsmouth-dominica*
region (region_id=17672) via the plain, unauthenticated
`/api/businesses?region_id=<id>` endpoint -- the previous Dominica pass only
walked the `roseau-dominica` region (id 1767) and left Portsmouth
uninvestigated. No Playwright / geolocation grant is needed for that listing
call; the earlier inventory's claim that the directory is location-gated
holds only for the `service_id=groceries&lat=&lng=` variant.

Largest food catalogue found for Dominica on any platform: 3,536 SKUs across
76 categories, led by "Groceries" (1,153), plus produce, frozen goods,
snacks, drinks and a small toiletries/pet/home minority. Payload `currency`
is XCD, matching countries.yaml dominica.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class SaversSupermarketDmSpider(CaribeEatsBaseSpider):
    name = "savers_supermarket_dm"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "savers-supermarket-"
