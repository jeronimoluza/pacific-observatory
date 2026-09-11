"""
Spider for Kaomini Niger (https://www.kaomini.ne/) -- "Kaomini | e-commerce",
a single-seller, cross-division general storefront serving Niamey, Niger.

Custom (non-platform-fingerprintable) PHP storefront. Product cards render
server-side on category listing pages (`div.product-cart-wrap`) -- no PDP
visit is required, and in fact the PDP page (the `..._show` URL) does NOT
re-render the price in raw HTML at all (verified live 2026-09-11: PDP HTML
carries the product name in <title> but no "Fcfa" text anywhere -- price
widget there is client-rendered). Listing pages are therefore the only
extraction point, following the centralboucherie_bf.py pattern.

Category taxonomy is fixed and enumerated from the site nav (34 categories,
IDs 1-40 with gaps) -- there is no sitemap.xml (/sitemap.xml and /robots.txt
both 404 to a custom "Kaomini | Page Erreur" page) and no cross-category
"all products" listing, so start_urls hardcodes the category slugs found on
https://www.kaomini.ne/ homepage nav, verified live 2026-09-11.

Catalog is SMALL (68 distinct products across all 34 categories) and mixed:
AGRO-ALIMENTAIRES (12, oils/honey/juices/tisanes), Specialite_Africaine (2),
Restaurant (16, prepared meals), RECHARGE_GAZ (2, cooking-gas refill),
Sante (32 across 2 pages), Cosmetique (11), Hygiene (1) -- most of the other
~26 categories (fashion, electronics, auto parts, etc.) returned 0 products
live. Left wide (coicop_codes unset in the manifest) like ekhumaisa_ne --
the classifier assigns COICOP leaves per product name.

Pagination: `?page=N` (1-indexed, page 1 == no param) -- confirmed live on
Sante_31_categorie (24 products page 1, 8 NEW + 6 repeated on page=2, 0 on
page=3) and empty (0 items) on page=2 for every other checked category.
Some page-to-page repeat is tolerated here (DuplicationPipeline dedups on
item["url"]); the stop condition is an empty page, capped defensively at
_MAX_PAGES per category.

CURRENCY: prices render as "2 000 Fcfa " (space thousands separator, no
decimal minor unit -- matches XOF's zero-decimal-subunit convention used
elsewhere in this country's manifests, e.g. daymarket_ne). All whitespace
(incl. non-breaking space) is stripped before parsing the digits.

product_id: a real SKU code embedded as free text in a nearby span
("PROD-20251201051629-842") -- no stable CSS class exists for it (empty
class="", inline style only), so it is extracted from the card's raw HTML
via regex rather than a CSS selector, matching the robustness pattern used
in centralboucherie_bf.py.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PROD_ID_RE = re.compile(r"PROD-[0-9-]+")
_MAX_PAGES = 10

_CATEGORY_SLUGS = [
    "Accessoires_21_categorie",
    "ACCESSOIRES_MOTO_25_categorie",
    "Appareils_de_cuisine_7_categorie",
    "ARTISANAT_27_categorie",
    "Bebes___enfants_23_categorie",
    "Bijouterie_9_categorie",
    "Boulangeries_patisseries_39_categorie",
    "Chauffage___climatisation_8_categorie",
    "Coffres_forts_et_accessoires_16_categorie",
    "Cosmetique_4_categorie",
    "Cuisine_Nigerienne_traditionnel_36_categorie",
    "Divers_13_categorie",
    "EPICES_40_categorie",
    "Femmes_22_categorie",
    "Fournitures_de_bureau_17_categorie",
    "Fournitures_scolaires_18_categorie",
    "Hommes_1_categorie",
    "Hygiene__30_categorie",
    "Jardinage_11_categorie",
    "Machines___accessoires_12_categorie",
    "MAISON_ET_AMEUBLEMENTS_29_categorie",
    "Materiel_informatique_19_categorie",
    "Materiels_de_soudure_10_categorie",
    "Materiels_de_surveillance_14_categorie",
    "PARFUMERIES_ENCENS_28_categorie",
    "PIECES_AUTO_26_categorie",
    "RECHARGE_GAZ_34_categorie",
    "Restaurant_2_categorie",
    "Restauration_rapide_Street_food_38_categorie",
    "Sacs___bagages_24_categorie",
    "Sante_31_categorie",
    "Specialite_Africaine_37_categorie",
    "Telephones_20_categorie",
    "AGRO-ALIMENTAIRES_6_categorie",
]


class KaominiNeSpider(scrapy.Spider):
    name = "kaomini_ne"
    allowed_domains = ["kaomini.ne"]
    start_urls = [f"https://www.kaomini.ne/{slug}" for slug in _CATEGORY_SLUGS]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    @staticmethod
    def _parse_price(text: str | None) -> float | None:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return None
        return float(digits)

    def parse(self, response, page=1):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.product-cart-wrap")
        if not cards:
            if page == 1:
                logger.warning(f"No product cards found on {response.url}")
            return

        for card in cards:
            name_link = card.css("div.product-content-wrap h2 a")
            product_name = (name_link.css("::text").get() or "").strip()
            href = name_link.attrib.get("href")
            url = response.urljoin(href) if href else response.url

            category = card.css("div.product-category a::text").get()
            category = category.strip() if category else None

            price_text = card.css("div.product-price span::text").get()
            price = self._parse_price(price_text)

            id_match = _PROD_ID_RE.search(card.get())
            product_id = id_match.group(0) if id_match else None

            if not product_name or price is None:
                logger.warning(
                    f"Could not extract product data from a card on {response.url}"
                )
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"Scraped {len(cards)} product cards from {response.url}")

        if page < _MAX_PAGES:
            next_page = page + 1
            base = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base}?page={next_page}",
                callback=self.parse,
                cb_kwargs={"page": next_page},
            )
