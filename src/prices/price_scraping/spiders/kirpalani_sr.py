"""
Kirpalani's (Suriname) -- https://www.kirpalani.com/.

General/home retailer (Magento 2, Luma theme, "BluebirdDay" storefront
skin). GraphQL (/graphql) and REST (/rest/V1/...) surfaces are both closed
(Cloudflare challenge / 401 unauthorized respectively) -- confirmed live
2026-09-01 -- so this uses MagentoSSRBaseSpider against the server-rendered
category HTML instead.

No grocery/food department: the full top-nav category list (47 links,
checked live 2026-09-01) has no "Levensmiddelen"/"Voeding"/"Supermarkt"
entry, and the "Groothandel" (wholesale) landing page renders zero
product-item cards -- it is an informational page, not a catalog. This is
a general/home-goods retailer (appliances, electronics, apparel,
furniture, hardware, toys, personal care) -- channel: dept-store, NOT
food.

Freshness check: a Brentwood 1L electric kettle priced at SRD 962.50 as of
2026-09-01, consistent with the post-devaluation SRD/USD rate (~USD 25
equivalent) -- not a stale pre-devaluation cache.

START_URLS is a hand-picked allowlist of the real product-category slugs
(as opposed to CMS/informational pages like /contact, /jobs, /over-ons,
/kirpalani-express*, /financiering, /levering, /groothandel -- confirmed
empty -- which share the same nav and would otherwise need to be filtered
out of a DISCOVERY_URL crawl anyway).
"""

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

_CATEGORY_SLUGS = [
    "apparaten",
    "auto-accessoires",
    "baby",
    "buitenshuis",
    "computer-accessoires",
    "dagelijkse-verzorging",
    "dames-mode",
    "decoratie",
    "dierbenodigdheden",
    "drogisterij",
    "elektronica",
    "exclusieve-deals",
    "gazon-en-tuin",
    "heren-mode",
    "huishouden",
    "ijzerwaren",
    "jongens-mode",
    "keukenapparaten",
    "koffer-reisaccessoires",
    "make-up",
    "meisjes-mode",
    "meubilair",
    "mode-accessoires",
    "naaimachines-fournituren",
    "school-en-kantoorbenodigdheden",
    "speelgoed",
    "sport-gym",
]


class KirpalaniSrSpider(MagentoSSRBaseSpider):
    name = "kirpalani_sr"
    allowed_domains = ["www.kirpalani.com"]
    currency = "SRD"
    language = "nl"
    START_URLS = [f"https://www.kirpalani.com/nl/{slug}" for slug in _CATEGORY_SLUGS]
