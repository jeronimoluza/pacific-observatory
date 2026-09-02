"""
Boutique ACM — Automobile Club de Monaco official shop,
https://boutiqueacm.com/.

Monaco's FIRST price source of any kind. Standard WooCommerce Store API, open
and unauthenticated: 122 products, EUR at currency_minor_unit=2
(price "1650" -> EUR 16.50 — the base class does the shift).

NOT a food source, and that is the point. Monaco has no grocery source and,
on the evidence, cannot have one: no Monaco-registered grocer exists at all.
carrefour.mc, monoprix.mc and spar.mc all fail DNS; casino.mc resolves to the
Société des Bains de Mer casino, not the French Casino supermarket chain. The
territory's grocery retail runs entirely on French national platforms
(courses.monoprix.fr, carrefour.fr/magasin/monaco, houra.fr).

This source deliberately SIDESTEPS the open policy question rather than
answering it. That question — whether a shared French national platform can
count as Monaco coverage, and under which country label — is still open and
still the user's to decide; onboarding courses.monoprix.fr here would risk
exact duplication against a future France pass building the same domain, and
double-count identical catalogues under two country labels. Boutique ACM has
no such problem: the Automobile Club de Monaco is the Monégasque institution
that organises the Monaco Grand Prix, the shop is Monaco-domiciled, and no
France onboarding pass would ever build it.

Also probed for Monaco this pass and rejected:
  - delovery.mc     genuine Cloudflare block — 403 on chrome124, chrome120,
                    chrome99 AND safari17_0 (all four TLS profiles, per the
                    mandatory gate). Monaco-domiciled food delivery, and the
                    best food lead the territory has; blocked, not absent.
  - houra.fr,       French national platforms. See the policy question above.
    carrefour.fr

Catalogue is Monaco Grand Prix apparel and merchandise (official GP tee-shirts,
GANT/ACM collections, silver grille badges), so mostly COICOP 03 with some 12
accessories — wide enough that coicop_codes is left unset for the classifier.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BoutiqueacmMcSpider(WooBaseSpider):
    name = "boutiqueacm_mc"
    allowed_domains = ["boutiqueacm.com"]
    currency = "EUR"
    language = "fr"
    BASE_URL = "https://boutiqueacm.com/wp-json/wc/store/v1/products"
