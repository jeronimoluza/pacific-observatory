"""
Spider for Kaynoo (Senegal) — https://www.kaynoo.sn/.

Magento GraphQL storefront. `categoryList`/`products` confirmed live
2026-08-06 via POST /graphql. Kaynoo is a general marketplace (electronics,
fashion, beauty dominate the root categories by product_count), so per the
WooBaseSpider/MagentoGraphQLBaseSpider convention of scoping a general
marketplace to its food-relevant subtree rather than walking the whole
catalog, this spider is scoped to the root category's ÉPICERIE ("grocery")
id=194 and its children (Petit déjeuner, Déjeuner/Diner, Nettoyage,
Alimentation Bébé, etc.) — walked via ROOT_CATEGORY_ID=194 (default
categoryList-then-paginate behaviour).

Verified: category 194 -> children incl. 'Petit déjeuner' (18), 'Divers'
(8); products(category_id:194) total_count=50, e.g. 'Poudre de Moringa
100% Naturel -1kg – NÉBÉDAY' XOF 9500, 'POUDRE DE CACAO BRUT - 100%
NATUREL - 250G' XOF 4000, 'Poudre De Petit Cola 100g – 100% Naturel' XOF
3000 — real, varied, local (mostly herbal/food-powder) products with
populated prices. Matches round 1's note that Kaynoo's food value is
depth on a handful of leaves, not catalog breadth.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class KaynooSnSpider(MagentoGraphQLBaseSpider):
    name = "kaynoo_sn"
    allowed_domains = ["kaynoo.sn"]
    currency = "XOF"
    language = "fr"
    GRAPHQL_URL = "https://www.kaynoo.sn/graphql"
    BASE_URL = "https://www.kaynoo.sn"
    ROOT_CATEGORY_ID = "194"
