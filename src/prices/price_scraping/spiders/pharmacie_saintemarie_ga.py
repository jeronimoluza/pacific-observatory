"""
Pharmacie Sainte Marie (pharmacie-saintemarie-gabon.com) -- Libreville, Gabon
pharmacy, WooCommerce.

Verified live 2026-09-01: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (X-WP-Total 1678 / X-WP-TotalPages
560 at per_page=3). The API's own prices.currency_code reports "XOF" (West
African CFA franc), which is wrong for Gabon -- this is a Central African
country and its currency is XAF. This looks like a shared "DigitecPharma"
multisite deployment (site footer/description; the operator also runs at
least one other Gabon pharmacy site) that never overrode the West-African
default. FORCE_CURRENCY="XAF" corrects this; currency_minor_unit=2 handling
is unaffected (base class still divides by 100).

Locality confirmed: physical address BP 1838, Libreville, Gabon; Click &
Collect + home delivery of medical equipment serving Libreville.

DECIMAL-PRICE TRAP (found in orchestrator review 2026-09-01): the base's
raw/10**currency_minor_unit division (minor_unit=2 here) is correct -- 4 of
1678 SKUs (e.g. "FORTE PHARMA Forté Royal Miel 24 pastilles", raw price
"1200010") land on a non-integer result (12000.1) because THIS SITE'S OWN
data carries a non-round centime residue, confirmed against the live
rendered PDP ("12 000,10 CFA" in the page's own price_html/DOM, not an
artifact of our fetch). XAF/XOF/FCFA has no real minor unit, so a decimal
price is a parse error downstream regardless of whose data produced it.
Rounding to the nearest whole franc here in the subclass (not in the shared
_woo_base, which other tenants' real-minor-unit currencies still need)
fixes exactly these 4 rows; 1674 of 1678 were already whole-XAF and
unaffected in either direction.

CATEGORY GAP: 491 of 1678 rows (29.3%) carry category: null. Checked
against the raw Store API payload directly (not just our extraction) --
these products genuinely return "categories": [] server-side, and their
live PDPs render no WooCommerce breadcrumb either (theme only shows one
when a category is assigned). Not recoverable from any field this API
exposes; left null rather than invented.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class PharmacieSaintemarieGaSpider(WooBaseSpider):
    name = "pharmacie_saintemarie_ga"
    allowed_domains = ["pharmacie-saintemarie-gabon.com"]
    currency = "XAF"
    language = "fr"
    BASE_URL = "https://pharmacie-saintemarie-gabon.com/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "XAF"

    def _item(self, p: dict):
        item = super()._item(p)
        if item and item.get("currency") == "XAF":
            # XAF has no minor unit; round away the rare non-round-centime
            # residue that a handful of this tenant's SKUs carry at source
            # (see DECIMAL-PRICE TRAP above) rather than ship a decimal.
            item["price"] = str(round(float(item["price"])))
        return item
