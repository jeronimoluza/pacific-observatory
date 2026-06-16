"""Auto-generated sub_labels for COICOP class 13.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "13.1.1.1": (
        SubLabel(
            id="electric-razors-hair-trimmers-and-epilators-hand-held-and-ho",
            label="electric razors, hair trimmers and epilators, hand-held and hood hairdryers, straightening irons, curling tongs and styling combs, sunlamps, vibrators, electric toothbrushes and other electric appliances for dental hygiene and so on",
            keywords_by_lang={
                "en": (
                    "electric razors, hair trimmers and epilators, hand-held and hood hairdryers, straightening irons, curling tongs and styling combs, sunlamps, vibrators, electric toothbrushes and other electric appliances for dental hygiene and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hairdryer",
            label="hairdryer",
            keywords_by_lang={"auto": ("hairdryer",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vibrator",
            label="vibrator",
            keywords_by_lang={"auto": ("vibrator",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-massager",
            label="Electric Massager",
            keywords_by_lang={
                "en": (
                    "Electric Massager",
                    "body massager",
                    "massage device",
                    "マッサージ器",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-razor",
            label="Electric Razor",
            keywords_by_lang={
                "en": ("Electric Razor", "electric shaver", "shaver", "髭剃り")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-toothbrush",
            label="Electric Toothbrush",
            keywords_by_lang={
                "en": ("Electric Toothbrush", "power toothbrush", "電動歯ブラシ")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-cleansing-brush",
            label="Facial Cleansing Brush",
            keywords_by_lang={
                "en": ("Facial Cleansing Brush", "sonic cleanser", "電動洗顔ブラシ")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-skincare-device",
            label="Facial Skincare Device",
            keywords_by_lang={
                "en": (
                    "Facial Skincare Device",
                    "beauty device",
                    "ems beauty tool",
                    "美顔器",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-dryer",
            label="Hair Dryer",
            keywords_by_lang={
                "en": (
                    "Hair Dryer",
                    "blow dryer",
                    "hairdryer",
                    "ម៉ាស៊ីនផ្លុំសក់",
                    "ヘアドライヤー",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-styling-tool",
            label="Hair Styling Tool",
            keywords_by_lang={
                "en": (
                    "Hair Styling Tool",
                    "curling iron",
                    "hair styler",
                    "straightening iron",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-trimmer",
            label="Hair Trimmer",
            keywords_by_lang={
                "en": ("Hair Trimmer", "beard trimmer", "clippers", "バリカン")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.1.1.2": (
        SubLabel(
            id="repair-of-electric-appliances-for-personal-care",
            label="repair of electric appliances for personal care",
            keywords_by_lang={
                "en": ("repair of electric appliances for personal care",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.1.2.0": (
        SubLabel(
            id="articles-for-personal-hygiene-toilet-soap-medicinal-soap-cle",
            label="articles for personal hygiene: toilet soap, medicinal soap, cleansing oil and milk, shaving soap, shaving cream and foam, toothpaste, epilation wax, paper handkerchiefs and so on",
            keywords_by_lang={
                "en": (
                    "articles for personal hygiene: toilet soap, medicinal soap, cleansing oil and milk, shaving soap, shaving cream and foam, toothpaste, epilation wax, paper handkerchiefs and so on",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="beauty-products-lipstick-nail-varnish-make-up-and-makeup-rem",
            label="beauty products: lipstick, nail varnish, make-up and makeup removal products (including powder compacts, brushes and powder puffs), hair lacquers and lotions, pre-shave and after-shave products, sunbathing products and sunscreens, hair removers, perfumes and toilet waters, personal deodorants, bath products and so on",
            keywords_by_lang={
                "en": (
                    "beauty products: lipstick, nail varnish, make-up and makeup removal products (including powder compacts, brushes and powder puffs), hair lacquers and lotions, pre-shave and after-shave products, sunbathing products and sunscreens, hair removers, perfumes and toilet waters, personal deodorants, bath products and so on",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-electric-appliances-shavers-razors-and-hair-trimmers-and",
            label="non-electric appliances: shavers, razors and hair trimmers and blades therefor, scissors, nail files, combs, shaving brushes, hairbrushes, toothbrushes, nail brushes, hairpins, curlers, personal weighing machines, scales and so on",
            keywords_by_lang={
                "en": (
                    "non-electric appliances: shavers, razors and hair trimmers and blades therefor, scissors, nail files, combs, shaving brushes, hairbrushes, toothbrushes, nail brushes, hairpins, curlers, personal weighing machines, scales and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bath-additives",
            label="bath additives",
            keywords_by_lang={"auto": ("bath additives",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="beauty-tool",
            label="beauty tool",
            keywords_by_lang={"auto": ("beauty tool",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="body-lotion",
            label="body lotion",
            keywords_by_lang={"auto": ("body lotion",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="body-wash",
            label="body wash",
            keywords_by_lang={"auto": ("body wash",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cotton-buds-pads",
            label="cotton buds pads",
            keywords_by_lang={"auto": ("cotton buds pads",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="deodorant",
            label="deodorant",
            keywords_by_lang={"auto": ("deodorant",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="eye-care",
            label="eye care",
            keywords_by_lang={"auto": ("eye care",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="face-mask",
            label="face mask",
            keywords_by_lang={"auto": ("face mask",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-cleanser",
            label="facial cleanser",
            keywords_by_lang={"auto": ("facial cleanser",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-serum",
            label="facial serum",
            keywords_by_lang={"auto": ("facial serum",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-toner",
            label="facial toner",
            keywords_by_lang={"auto": ("facial toner",)},
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="feminine-hygiene-product",
            label="feminine hygiene product",
            keywords_by_lang={"auto": ("feminine hygiene product",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="feminine-wash",
            label="feminine wash",
            keywords_by_lang={"auto": ("feminine wash",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-color",
            label="hair color",
            keywords_by_lang={"auto": ("hair color",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-conditioner",
            label="hair conditioner",
            keywords_by_lang={"auto": ("hair conditioner",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-styling-product",
            label="hair styling product",
            keywords_by_lang={"auto": ("hair styling product",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-treatment",
            label="hair treatment",
            keywords_by_lang={"auto": ("hair treatment",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hand-cream",
            label="hand cream",
            keywords_by_lang={"auto": ("hand cream",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lip-balm",
            label="lip balm",
            keywords_by_lang={"auto": ("lip balm",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lipstick",
            label="lipstick",
            keywords_by_lang={"auto": ("lipstick",)},
            allowed_bases=frozenset({"item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="makeup",
            label="makeup",
            keywords_by_lang={"auto": ("makeup",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="manual-razor",
            label="manual razor",
            keywords_by_lang={"auto": ("manual razor",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mouthwash",
            label="mouthwash",
            keywords_by_lang={"auto": ("mouthwash",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nail-polish",
            label="nail polish",
            keywords_by_lang={"auto": ("nail polish",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="oral-care-accessory",
            label="oral care accessory",
            keywords_by_lang={"auto": ("oral care accessory",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="perfume",
            label="perfume",
            keywords_by_lang={"auto": ("perfume",)},
            allowed_bases=frozenset({"volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="scrub-exfoliant",
            label="scrub exfoliant",
            keywords_by_lang={"auto": ("scrub exfoliant",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="shampoo",
            label="shampoo",
            keywords_by_lang={"auto": ("shampoo",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="soap",
            label="soap",
            keywords_by_lang={"auto": ("soap",)},
            allowed_bases=frozenset({"item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sunscreen",
            label="sunscreen",
            keywords_by_lang={"auto": ("sunscreen",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toothbrush",
            label="toothbrush",
            keywords_by_lang={"auto": ("toothbrush",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toothpaste",
            label="toothpaste",
            keywords_by_lang={"auto": ("toothpaste",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cosmetic-and-makeup-products",
            label="Cosmetic And Makeup Products",
            keywords_by_lang={
                "en": (
                    "Cosmetic And Makeup Products",
                    "lipstick",
                    "makeup powder",
                    "nail varnish",
                    "powder compact",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-care-products",
            label="Dental Care Products",
            keywords_by_lang={
                "en": (
                    "Dental Care Products",
                    "dental floss",
                    "mouthwash",
                    "toothbrush",
                    "toothpaste",
                )
            },
            allowed_bases=frozenset({"item", "count", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fragrances-and-perfumes",
            label="Fragrances And Perfumes",
            keywords_by_lang={
                "en": (
                    "Fragrances And Perfumes",
                    "cologne",
                    "kids fragrance",
                    "perfume",
                    "toilet water",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-styling-and-care-products",
            label="Hair Styling And Care Products",
            keywords_by_lang={
                "en": (
                    "Hair Styling And Care Products",
                    "hair lacquer",
                    "hair lotion",
                    "hair shaper",
                    "styling wax",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="manual-razors-and-blades",
            label="Manual Razors And Blades",
            keywords_by_lang={
                "en": (
                    "Manual Razors And Blades",
                    "cartridge razors",
                    "razor blades",
                    "shavers",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="personal-hygiene-paper-products",
            label="Personal Hygiene Paper Products",
            keywords_by_lang={
                "en": (
                    "Personal Hygiene Paper Products",
                    "facial tissues",
                    "paper handkerchiefs",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="shaving-preparation-products",
            label="Shaving Preparation Products",
            keywords_by_lang={
                "en": (
                    "Shaving Preparation Products",
                    "pre-shave lotion",
                    "shave gel",
                    "shaving cream",
                    "shaving foam",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="skincare-and-sunscreen-products",
            label="Skincare And Sunscreen Products",
            keywords_by_lang={
                "en": (
                    "Skincare And Sunscreen Products",
                    "face cream",
                    "lip balm",
                    "moisturiser",
                    "sunscreen",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toilet-soaps-and-washes",
            label="Toilet Soaps And Washes",
            keywords_by_lang={
                "en": (
                    "Toilet Soaps And Washes",
                    "bar soap",
                    "body wash",
                    "liquid hand wash",
                    "shower gel",
                )
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.1.3.1": (
        SubLabel(
            id="hairdressing-salons-or-barbers-for-women-men-and-children",
            label="hairdressing salons or barbers for women, men and children",
            keywords_by_lang={
                "en": ("hairdressing salons or barbers for women, men and children",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.1.3.2": (
        SubLabel(
            id="diet-clubs-and-tattoo-and-piercing-services",
            label="diet clubs and tattoo and piercing services",
            keywords_by_lang={"en": ("diet clubs and tattoo and piercing services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="facial-beauty-treatments-depilation-solarium-pedicure-body-c",
            label="facial beauty treatments, depilation, solarium, pedicure, body care, manicure, thalassotherapy, Turkish baths, saunas, non-medical massages and so on",
            keywords_by_lang={
                "en": (
                    "facial beauty treatments, depilation, solarium, pedicure, body care, manicure, thalassotherapy, Turkish baths, saunas, non-medical massages and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.2.1.1": (
        SubLabel(
            id="costume-jewellery-cuff-links-and-tiepins",
            label="costume jewellery, cuff links and tiepins",
            keywords_by_lang={"en": ("costume jewellery, cuff links and tiepins",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="precious-stones-and-metals-and-jewellery-fashioned-out-of-su",
            label="precious stones and metals and jewellery fashioned out of such stones and metals",
            keywords_by_lang={
                "en": (
                    "precious stones and metals and jewellery fashioned out of such stones and metals",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="watches-and-stopwatches",
            label="watches and stopwatches",
            keywords_by_lang={"en": ("watches and stopwatches",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bracelet",
            label="bracelet",
            keywords_by_lang={"auto": ("bracelet",)},
            allowed_bases=frozenset({"item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="earrings",
            label="earrings",
            keywords_by_lang={"auto": ("earrings",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="necklace",
            label="necklace",
            keywords_by_lang={"auto": ("necklace",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="ring",
            label="ring",
            keywords_by_lang={"auto": ("ring",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="watch",
            label="watch",
            keywords_by_lang={"auto": ("watch",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="costume-jewellery",
            label="Costume Jewellery",
            keywords_by_lang={
                "en": (
                    "Costume Jewellery",
                    "costume accessories",
                    "fashion jewelry",
                    "imitation jewelry",
                    "合金アクセサリー",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cuff-links-tiepins",
            label="Cuff Links And Tiepins",
            keywords_by_lang={
                "en": (
                    "Cuff Links And Tiepins",
                    "cufflinks",
                    "tie bar",
                    "tie clip",
                    "tie tack",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gold-silver-jewelry",
            label="Gold And Silver Jewellery",
            keywords_by_lang={
                "en": (
                    "Gold And Silver Jewellery",
                    "fine jewellery",
                    "gold necklace",
                    "k18 gold jewelry",
                    "pure gold pendant",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pearl-jewellery",
            label="Pearl Jewellery",
            keywords_by_lang={
                "en": (
                    "Pearl Jewellery",
                    "pearl necklace",
                    "shell pearl necklace",
                    "真珠ネックレス",
                    "貝パール",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="stopwatches",
            label="Stopwatches",
            keywords_by_lang={
                "en": ("Stopwatches", "chronograph watch", "lap timer", "timer watch")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wrist-watches",
            label="Wrist Watches",
            keywords_by_lang={
                "en": (
                    "Wrist Watches",
                    "analog watch",
                    "wristwatch",
                    "クォーツ時計",
                    "機械式腕時計",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.2.1.2": (
        SubLabel(
            id="hire-of-jewellery-clocks-and-watches",
            label="hire of jewellery, clocks and watches",
            keywords_by_lang={"en": ("hire of jewellery, clocks and watches",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="remodelling-of-jewellery",
            label="remodelling of jewellery",
            keywords_by_lang={"en": ("remodelling of jewellery",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-jewellery-clocks-and-watches",
            label="repair of jewellery, clocks and watches",
            keywords_by_lang={"en": ("repair of jewellery, clocks and watches",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.2.2.0": (
        SubLabel(
            id="articles-to-be-used-in-religious-and-ritual-celebrations",
            label="articles to be used in religious and ritual celebrations",
            keywords_by_lang={
                "en": ("articles to be used in religious and ritual celebrations",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="religious-and-ritual-articles-such-as-crucifixes-and-rosarie",
            label="religious and ritual articles, such as crucifixes and rosaries, figurines, pictures, votive candles, amulets, strips of paper with prayers, menorah chandeliers, advent wreaths and others",
            keywords_by_lang={
                "en": (
                    "religious and ritual articles, such as crucifixes and rosaries, figurines, pictures, votive candles, amulets, strips of paper with prayers, menorah chandeliers, advent wreaths and others",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.2.9.1": (
        SubLabel(
            id="articles-for-babies-diapers-nappies-of-any-material-baby-car",
            label="articles for babies: diapers (nappies) of any material, baby carriages, pushchairs/strollers, carrycots, recliners, back carriers, front carriers, harnesses for babies and so on",
            keywords_by_lang={
                "en": (
                    "articles for babies: diapers (nappies) of any material, baby carriages, pushchairs/strollers, carrycots, recliners, back carriers, front carriers, harnesses for babies and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="articles-for-smokers-pipes-lighters-cigarette-cases-cigar-cu",
            label="articles for smokers: pipes, lighters, cigarette cases, cigar cutters, ashtrays, electronic cigarette devices and so on",
            keywords_by_lang={
                "en": (
                    "articles for smokers: pipes, lighters, cigarette cases, cigar cutters, ashtrays, electronic cigarette devices and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="funerary-articles-coffins-gravestones-urns-burial-shrouds-an",
            label="funerary articles: coffins, gravestones, urns, burial shrouds, and so on",
            keywords_by_lang={
                "en": (
                    "funerary articles: coffins, gravestones, urns, burial shrouds, and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="lighter-fuel-wall-thermometers-and-barometers",
            label="lighter fuel; wall thermometers and barometers",
            keywords_by_lang={
                "en": ("lighter fuel; wall thermometers and barometers",)
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="miscellaneous-personal-articles-non-corrective-sunglasses-pr",
            label="miscellaneous personal articles: non-corrective sunglasses, protective glasses, umbrellas and parasols, fans, key rings, pill organizers, ear plugs and so on",
            keywords_by_lang={
                "en": (
                    "miscellaneous personal articles: non-corrective sunglasses, protective glasses, umbrellas and parasols, fans, key rings, pill organizers, ear plugs and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="travel-goods-and-other-carriers-of-personal-effects-suitcase",
            label="travel goods and other carriers of personal effects: suitcases, trunks, travel bags, attaché cases, satchels, handbags, wallets, purses, backpacks for school and travel and so on",
            keywords_by_lang={
                "en": (
                    "travel goods and other carriers of personal effects: suitcases, trunks, travel bags, attaché cases, satchels, handbags, wallets, purses, backpacks for school and travel and so on",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="baby-accessory",
            label="baby accessory",
            keywords_by_lang={"auto": ("baby accessory",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="backpack",
            label="backpack",
            keywords_by_lang={"auto": ("backpack",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bag",
            label="bag",
            keywords_by_lang={"auto": ("bag",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bag-charm",
            label="bag charm",
            keywords_by_lang={"auto": ("bag charm",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="diapers",
            label="diapers",
            keywords_by_lang={"auto": ("diapers",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="feminine-hygiene-product",
            label="feminine hygiene product",
            keywords_by_lang={"auto": ("feminine hygiene product",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hair-accessory",
            label="hair accessory",
            keywords_by_lang={"auto": ("hair accessory",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="handbag",
            label="handbag",
            keywords_by_lang={"auto": ("handbag",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="key-ring",
            label="key ring",
            keywords_by_lang={"auto": ("key ring",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lapel-pin",
            label="lapel pin",
            keywords_by_lang={"auto": ("lapel pin",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="makeup-applicator",
            label="makeup applicator",
            keywords_by_lang={"auto": ("makeup applicator",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="phone-lanyard",
            label="phone lanyard",
            keywords_by_lang={"auto": ("phone lanyard",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="suitcase",
            label="suitcase",
            keywords_by_lang={"auto": ("suitcase",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sunglasses",
            label="sunglasses",
            keywords_by_lang={"auto": ("sunglasses",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="travel-organizer",
            label="travel organizer",
            keywords_by_lang={"auto": ("travel organizer",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="umbrella",
            label="umbrella",
            keywords_by_lang={"auto": ("umbrella",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wallet",
            label="wallet",
            keywords_by_lang={"auto": ("wallet",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.2.9.2": (
        SubLabel(
            id="hire-of-other-personal-effects",
            label="hire of other personal effects",
            keywords_by_lang={"en": ("hire of other personal effects",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-other-personal-effects",
            label="repair of other personal effects",
            keywords_by_lang={"en": ("repair of other personal effects",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.3.0.1": (
        SubLabel(
            id="child-minding-outside-the-home-including-after-school-center",
            label="child-minding outside the home, including after-school centers, nurseries, day-care facilities, wet nurses, crèches, kindergartens (other than educational), play schools and other child-minding facilities",
            keywords_by_lang={
                "en": (
                    "child-minding outside the home, including after-school centers, nurseries, day-care facilities, wet nurses, crèches, kindergartens (other than educational), play schools and other child-minding facilities",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.3.0.2": (
        SubLabel(
            id="non-medical-residences-for-disabled-or-maladjusted-persons",
            label="non-medical residences for disabled or maladjusted persons",
            keywords_by_lang={
                "en": ("non-medical residences for disabled or maladjusted persons",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-medical-retirement-homes-for-elderly-persons",
            label="non-medical retirement homes for elderly persons",
            keywords_by_lang={
                "en": ("non-medical retirement homes for elderly persons",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.3.0.3": (
        SubLabel(
            id="help-to-maintain-elderly-and-disabled-persons-at-home-home-c",
            label="help to maintain elderly and disabled persons at home (home-cleaning services, meal programmes, day-care centres, day-care services and holiday-care services)",
            keywords_by_lang={
                "en": (
                    "help to maintain elderly and disabled persons at home (home-cleaning services, meal programmes, day-care centres, day-care services and holiday-care services)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.3.0.9": (
        SubLabel(
            id="guidance-arbitration-fostering-and-adoption-services-for-fam",
            label="guidance, arbitration, fostering and adoption services for families",
            keywords_by_lang={
                "en": (
                    "guidance, arbitration, fostering and adoption services for families",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="schools-for-disabled-persons-where-the-main-aim-is-to-help-s",
            label="schools for disabled persons where the main aim is to help students to overcome their disability",
            keywords_by_lang={
                "en": (
                    "schools for disabled persons where the main aim is to help students to overcome their disability",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.9.0.1": (
        SubLabel(
            id="services-provided-by-prostitutes-sex-workers-and-the-like",
            label="services provided by prostitutes, sex workers and the like",
            keywords_by_lang={
                "en": ("services provided by prostitutes, sex workers and the like",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.9.0.2": (
        SubLabel(
            id="expenditures-for-religious-services-e-g-requiem-baptizing-an",
            label="expenditures for religious services (e.g., requiem, baptizing and marriage services)",
            keywords_by_lang={
                "en": (
                    "expenditures for religious services (e.g., requiem, baptizing and marriage services)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "13.9.0.9": (
        SubLabel(
            id="expenditures-for-non-religious-services-and-events-such-as-c",
            label="expenditures for non-religious services and events, such as coming-of-age celebrations in Latin-American “quince” or debutante balls",
            keywords_by_lang={
                "en": (
                    "expenditures for non-religious services and events, such as coming-of-age celebrations in Latin-American “quince” or debutante balls",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fees-for-legal-services-employment-agencies-and-so-on",
            label="fees for legal services, employment agencies and so on",
            keywords_by_lang={
                "en": ("fees for legal services, employment agencies and so on",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fees-for-the-issue-of-birth-marriage-and-death-certificates-",
            label="fees for the issue of birth, marriage and death certificates and other administrative documents",
            keywords_by_lang={
                "en": (
                    "fees for the issue of birth, marriage and death certificates and other administrative documents",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="firearm-licences",
            label="firearm licences",
            keywords_by_lang={"en": ("firearm licences",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="newspaper-notices-and-advertisements",
            label="newspaper notices and advertisements",
            keywords_by_lang={"en": ("newspaper notices and advertisements",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="photocopies-and-other-reproductions-of-documents",
            label="photocopies and other reproductions of documents",
            keywords_by_lang={
                "en": ("photocopies and other reproductions of documents",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-estate-agents-housing-agents-auctioneers-salesro",
            label="services of estate agents, housing agents, auctioneers, salesroom operators and other intermediaries",
            keywords_by_lang={
                "en": (
                    "services of estate agents, housing agents, auctioneers, salesroom operators and other intermediaries",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-graphologists-astrologers-palmists-private-detec",
            label="services of graphologists, astrologers, palmists, private detectives, bodyguards, dating services, matrimonial agencies and marriage guidance counsellors, public writers, miscellaneous concessions (seats, toilets and cloakrooms) and so on",
            keywords_by_lang={
                "en": (
                    "services of graphologists, astrologers, palmists, private detectives, bodyguards, dating services, matrimonial agencies and marriage guidance counsellors, public writers, miscellaneous concessions (seats, toilets and cloakrooms) and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-lawyers-accountants-and-so-on",
            label="services of lawyers, accountants and so on",
            keywords_by_lang={"en": ("services of lawyers, accountants and so on",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-undertakers-and-other-funeral-services",
            label="services of undertakers and other funeral services",
            keywords_by_lang={
                "en": ("services of undertakers and other funeral services",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
}
