"""Per-spider Common Crawl config + default index set.

Extracted from ``cc_warc_fetcher.py`` (which was over the 500-line cap).
``cc_warc_fetcher`` imports :data:`SPIDER_CC_CONFIG` and
:data:`DEFAULT_CC_INDEXES` from here.
"""

from __future__ import annotations

from typing import Dict, List

# Curated default CC-MAIN indexes — the most recent monthly crawls, verified
# live against https://index.commoncrawl.org/collinfo.json (2026-08-04).
# Used by the `common-crawl` CLI when no --index is passed. Keep small + current;
# more indexes = more historical coverage but proportionally more index queries.
DEFAULT_CC_INDEXES: List[str] = [
    "CC-MAIN-2026-30",
    "CC-MAIN-2026-25",
    "CC-MAIN-2026-21",
    "CC-MAIN-2026-17",
    "CC-MAIN-2026-12",
    "CC-MAIN-2026-08",
    "CC-MAIN-2026-04",
    "CC-MAIN-2025-51",
]

# Per-spider CC config:
#   prefix  — URL prefix to feed CC index (matchType=prefix). Pick the narrowest
#             prefix that still covers all product detail pages.
#   path_re — regex applied to URL path to keep only product detail pages
#             (filters out homepage / category / static assets that share the prefix).
SPIDER_CC_CONFIG: Dict[str, Dict[str, str]] = {
    "guardian_sg": {"prefix": "www.guardian.com.sg/", "path_re": r"/[^/]+/p/\d+"},
    "mannings": {"prefix": "www.mannings.com.hk/", "path_re": r"/[^/]+/p/\d+"},
    # guardian.com.my uses a PWA SPA (Adobe Venia) — CC archives are JS shells with no
    # product data in the initial HTML. prefix covers both www and no-www; path_re matches
    # root-level product slugs (/<slug>.html). Usable CC data unlikely until site adds SSR.
    "guardian_my": {"prefix": "guardian.com.my/", "path_re": r"^/[^/]+\.html$"},
    "cosmed": {
        "prefix": "shop.cosmed.com.tw/SalePage/",
        "path_re": r"/SalePage/Index/",
    },
    "boots_th": {
        "prefix": "store.boots.co.th/ecommerce/",
        "path_re": r"/ecommerce/\d+",
    },
    "aldi_au": {
        "prefix": "www.aldi.com.au/product/",
        "path_re": r"^/product/[^/]+",
    },
    # Tier 1 additions (2026-05-06)
    # CitySuper HK is a multi-subdomain Shopify store. Product pages archived by CC
    # live under logon.citysuper.com.hk (648 in CC-MAIN-2024-51) and
    # bearwithlove.citysuper.com.hk / hamper.citysuper.com.hk (92 in CC-MAIN-2023-50).
    # www.citysuper.com.hk/products/ has zero CC captures.
    # Run a second pass with prefix=bearwithlove.citysuper.com.hk/ to pick up the older records.
    "citysuper_hk": {
        "prefix": "logon.citysuper.com.hk/products/",
        "path_re": r"^/products/[^/?]+",
    },
    "cold_storage_sg": {
        "prefix": "www.coldstorage.com.sg/",
        "path_re": r"/product/[^/?]+",
    },
    "carrefour_tw": {
        "prefix": "online.carrefour.com.tw/",
        "path_re": r"/[^/?]+\.html",
    },
    # --- Vanuatu ---
    "dynamic_vanuatu": {
        "prefix": "retail.dynamicvanuatu.com/products/",
        "path_re": r"^/products/[^/?]+",
    },
    # --- Mongolia ---
    "citypharm": {
        "prefix": "citypharm.mn/shop/",
        "path_re": r"^/shop/\d+-",
    },
    # --- Malaysia ---
    "doctor_oncall": {
        "prefix": "www.doctoroncall.com.my/pharmacy/",
        # Product pages: /pharmacy/<slug> — exactly one path segment after /pharmacy/
        # Excludes category sub-paths like /pharmacy/medicines/weight-loss
        "path_re": r"^/pharmacy/[^/]+/?$",
    },
    # --- Thailand ---
    "exta": {
        "prefix": "www.exta.co.th/product/",
        "path_re": r"^/product/[^/]+",
    },
    # --- Singapore ---
    "fairprice": {
        "prefix": "www.fairprice.com.sg/product/",
        "path_re": r"^/product/[^/?]+",
    },
    # --- Papua New Guinea ---
    "food_pro": {
        "prefix": "fpr.com.pg/product/",
        "path_re": r"^/product/[^/?]+",
    },
    # --- Japan ---
    "horizon_farms": {
        "prefix": "en.horizonfarms.jp/products/",
        "path_re": r"^/products/[^/?]+",
    },
    # --- Indonesia ---
    "hypermart": {
        "prefix": "shop.hypermart.co.id/hypermart/product/",
        "path_re": r"^/hypermart/product/[^/?]+",
    },
    # --- China ---
    "jianke": {
        "prefix": "www.jianke.com/product/",
        "path_re": r"^/product/\d+\.html$",
    },
    "pharmacy_111": {
        "prefix": "m.111.com.cn/item/",
        "path_re": r"^/item/\d+\.html$",
    },
    # --- Cambodia ---
    "makro": {
        "prefix": "www.makrocambodiaclick.com/en/products/",
        "path_re": r"^/en/products/\d+",
    },
    # --- Fiji ---
    "mh_online": {
        "prefix": "mh.com.fj/product/",
        "path_re": r"^/product/[^/?]+",
    },
    "rbpatel": {
        "prefix": "rbpatel.com.fj/product/",
        "path_re": r"^/product/[^/?]+",
    },
    # --- Tonga ---
    "molisi": {
        "prefix": "molisi.to/",
        "path_re": r"^/(baby-maternity|beverage|grocery|meat-seafood|personal-care)/[^/?]+",
    },
    # --- Samoa ---
    "samoa_market": {
        "prefix": "samoamarket.com/products/",
        "path_re": r"^/products/[^/?]+",
    },
    # --- Philippines ---
    "pickaroo": {
        "prefix": "pickaroo.com/",
        "path_re": r"^/[^/]+/products/[^/]+/product-detail/\d+",
    },
    "south_star_drug": {
        "prefix": "southstardrug.com.ph/products/",
        "path_re": r"^/products/[^/?]+",
    },
    # --- Japan ---
    "rakuten": {
        # Product detail pages: item.rakuten.co.jp/<shop>/<item>/
        # Excludes category-listing pages which have /c/<id> as the second segment
        "prefix": "item.rakuten.co.jp/",
        "path_re": r"^/[^/]+/(?!c/)[^/]+",
    },
    # --- Vietnam ---
    "tiki": {
        # Product pages: tiki.vn/<slug>-p<id>.html (all at root, no category prefix)
        "prefix": "tiki.vn/",
        "path_re": r"^/[^/]+-p\d+\.html$",
    },
}
