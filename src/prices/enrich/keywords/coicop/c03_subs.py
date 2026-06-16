"""Auto-generated sub_labels for COICOP class 03.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "03.1.1.0": (
        SubLabel(
            id="clothing-materials-of-natural-synthetic-and-mixed-fibres",
            label="clothing materials of natural, synthetic and mixed fibres",
            keywords_by_lang={
                "en": ("clothing materials of natural, synthetic and mixed fibres",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="leather-fur-fusible-webbing-wadding-and-felt-filling-for-mak",
            label="leather, fur, fusible webbing, wadding and felt filling for making wearing apparel",
            keywords_by_lang={
                "en": (
                    "leather, fur, fusible webbing, wadding and felt filling for making wearing apparel",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fabric-textile",
            label="Clothing fabric",
            keywords_by_lang={
                "en": (
                    "Clothing fabric",
                    "clothing material",
                    "dressmaking fabric",
                    "fabric",
                    "sewing fabric",
                    "textile",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="leather-material",
            label="Leather and fur materials",
            keywords_by_lang={
                "en": (
                    "Leather and fur materials",
                    "faux fur",
                    "hide",
                    "leather for clothing",
                    "real fur",
                    "suede",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="natural-fiber-fabric",
            label="Natural fiber fabric",
            keywords_by_lang={
                "en": (
                    "Natural fiber fabric",
                    "cotton fabric",
                    "linen fabric",
                    "silk fabric",
                    "wool fabric",
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
            id="sewing-notions-fillings",
            label="Sewing materials and fillings",
            keywords_by_lang={
                "en": (
                    "Sewing materials and fillings",
                    "batting",
                    "felt filling",
                    "fusible webbing",
                    "interfacing",
                    "sewing stuffing",
                    "wadding",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="synthetic-fabric",
            label="Synthetic fabric",
            keywords_by_lang={
                "en": (
                    "Synthetic fabric",
                    "nylon fabric",
                    "polyester fabric",
                    "rayon fabric",
                    "spandex fabric",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.2.1": (
        SubLabel(
            id="capes-overcoats-raincoats-anoraks-parkas-jackets-trousers-wa",
            label="capes, overcoats, raincoats, anoraks, parkas, jackets, trousers, waistcoats, suits, costumes, etc.",
            keywords_by_lang={
                "en": (
                    "capes, overcoats, raincoats, anoraks, parkas, jackets, trousers, waistcoats, suits, costumes, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pyjamas-dressing-gowns-bathrobes-etc",
            label="pyjamas, dressing gowns, bathrobes, etc.",
            keywords_by_lang={"en": ("pyjamas, dressing gowns, bathrobes, etc.",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shirts-pullovers-sweaters-cardigans-shorts-swimsuits-tracksu",
            label="shirts, pullovers, sweaters, cardigans, shorts, swimsuits, tracksuits, jogging suits, sweatshirts, T-shirts, leotards, etc.",
            keywords_by_lang={
                "en": (
                    "shirts, pullovers, sweaters, cardigans, shorts, swimsuits, tracksuits, jogging suits, sweatshirts, T-shirts, leotards, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="traditional-garments",
            label="traditional garments",
            keywords_by_lang={
                "en": (
                    "traditional garments",
                    "Traditional garments",
                    "cultural dress",
                    "ethnic wear",
                    "traditional clothing",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vests-underpants-socks-etc",
            label="vests, underpants, socks, etc.",
            keywords_by_lang={"en": ("vests, underpants, socks, etc.",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="boys-clothing",
            label="boys clothing",
            keywords_by_lang={"auto": ("boys clothing",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-coat",
            label="mens coat",
            keywords_by_lang={"auto": ("mens coat",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-jumper",
            label="mens jumper",
            keywords_by_lang={"auto": ("mens jumper",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-shirt",
            label="mens shirt",
            keywords_by_lang={"auto": ("mens shirt",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-shorts",
            label="mens shorts",
            keywords_by_lang={"auto": ("mens shorts",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-t-shirt",
            label="mens t shirt",
            keywords_by_lang={"auto": ("mens t shirt",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-trousers",
            label="mens trousers",
            keywords_by_lang={"auto": ("mens trousers",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-activewear",
            label="Men's activewear",
            keywords_by_lang={
                "en": (
                    "Men's activewear",
                    "jogging suits",
                    "leotards",
                    "shorts",
                    "swimsuits",
                    "tracksuits",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-outerwear",
            label="Men's outerwear",
            keywords_by_lang={
                "en": (
                    "Men's outerwear",
                    "anoraks",
                    "capes",
                    "jackets",
                    "overcoats",
                    "parkas",
                    "raincoats",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-tops-casual",
            label="Men's shirts and tops",
            keywords_by_lang={
                "en": (
                    "Men's shirts and tops",
                    "cardigans",
                    "pullovers",
                    "shirts",
                    "sweaters",
                    "sweatshirts",
                    "t-shirts",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-sleepwear-loungewear",
            label="Men's sleepwear and loungewear",
            keywords_by_lang={
                "en": (
                    "Men's sleepwear and loungewear",
                    "bathrobes",
                    "dressing gowns",
                    "pyjamas",
                    "robes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-suits-trousers",
            label="Men's suits and trousers",
            keywords_by_lang={
                "en": (
                    "Men's suits and trousers",
                    "costumes",
                    "dress pants",
                    "suits",
                    "trousers",
                    "waistcoats",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-underwear-socks",
            label="Men's underwear and socks",
            keywords_by_lang={
                "en": (
                    "Men's underwear and socks",
                    "boxers",
                    "briefs",
                    "socks",
                    "underpants",
                    "underwear",
                    "vests",
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
    ),
    "03.1.2.2": (
        SubLabel(
            id="capes-overcoats-raincoats-anoraks-parkas-blousons-jackets-tr",
            label="capes, overcoats, raincoats, anoraks, parkas, blousons, jackets, trousers, waistcoats, suits, costumes, dresses, skirts, etc.",
            keywords_by_lang={
                "en": (
                    "capes, overcoats, raincoats, anoraks, parkas, blousons, jackets, trousers, waistcoats, suits, costumes, dresses, skirts, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pyjamas-nightshirts-nightdresses-housecoats-dressing-gowns-b",
            label="pyjamas, nightshirts, nightdresses, housecoats, dressing gowns, bathrobes, etc.",
            keywords_by_lang={
                "en": (
                    "pyjamas, nightshirts, nightdresses, housecoats, dressing gowns, bathrobes, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shirts-blouses-pullovers-sweaters-cardigans-shorts-swimsuits",
            label="shirts, blouses, pullovers, sweaters, cardigans, shorts, swimsuits, tracksuits, jogging suits, sweatshirts, t-shirts, leotards, etc.",
            keywords_by_lang={
                "en": (
                    "shirts, blouses, pullovers, sweaters, cardigans, shorts, swimsuits, tracksuits, jogging suits, sweatshirts, t-shirts, leotards, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="traditional-garments",
            label="traditional garments",
            keywords_by_lang={"en": ("traditional garments",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vests-underpants-socks-stockings-tights-petticoats-brassiere",
            label="vests, underpants, socks, stockings, tights, petticoats, brassieres, knickers, slips, girdles, corsets, body stockings, etc.",
            keywords_by_lang={
                "en": (
                    "vests, underpants, socks, stockings, tights, petticoats, brassieres, knickers, slips, girdles, corsets, body stockings, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-coat",
            label="womens coat",
            keywords_by_lang={"auto": ("womens coat",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-dress",
            label="womens dress",
            keywords_by_lang={"auto": ("womens dress",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-jumper",
            label="womens jumper",
            keywords_by_lang={"auto": ("womens jumper",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-skirt",
            label="womens skirt",
            keywords_by_lang={"auto": ("womens skirt",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-sportswear",
            label="womens sportswear",
            keywords_by_lang={"auto": ("womens sportswear",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-top",
            label="womens top",
            keywords_by_lang={"auto": ("womens top",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-trousers",
            label="womens trousers",
            keywords_by_lang={"auto": ("womens trousers",)},
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
        SubLabel(
            id="traditional-garment",
            label="Traditional garments",
            keywords_by_lang={
                "en": (
                    "Traditional garments",
                    "cultural garments",
                    "ethnic wear",
                    "traditional clothing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="activewear",
            label="Women's activewear",
            keywords_by_lang={
                "en": (
                    "Women's activewear",
                    "athletic wear",
                    "jogging suit",
                    "leotard",
                    "sports bra",
                    "sweatshirt",
                    "tracksuit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="outerwear-coat-jacket",
            label="Women's coats and jackets",
            keywords_by_lang={
                "en": (
                    "Women's coats and jackets",
                    "anorak",
                    "blouson",
                    "cape",
                    "coat",
                    "jacket",
                    "overcoat",
                    "parka",
                    "raincoat",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="suit-dress-formal",
            label="Women's dresses and suits",
            keywords_by_lang={
                "en": (
                    "Women's dresses and suits",
                    "costume suit",
                    "dress",
                    "evening gown",
                    "formal dress",
                    "skirt suit",
                    "women's suit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hosiery-socks",
            label="Women's hosiery and socks",
            keywords_by_lang={
                "en": (
                    "Women's hosiery and socks",
                    "pantyhose",
                    "socks",
                    "stockings",
                    "tights",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="knitwear-sweater-cardigan",
            label="Women's knitwear",
            keywords_by_lang={
                "en": (
                    "Women's knitwear",
                    "cardigan",
                    "jumper",
                    "knit top",
                    "pullover",
                    "sweater",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sleepwear-loungewear",
            label="Women's sleepwear and loungewear",
            keywords_by_lang={
                "en": (
                    "Women's sleepwear and loungewear",
                    "bathrobe",
                    "dressing gown",
                    "housecoat",
                    "nightdress",
                    "nightshirt",
                    "pyjamas",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="swimwear",
            label="Women's swimwear",
            keywords_by_lang={
                "en": (
                    "Women's swimwear",
                    "bathing suit",
                    "beachwear",
                    "bikini",
                    "swimsuit",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tops-blouse-shirt",
            label="Women's tops, shirts, and blouses",
            keywords_by_lang={
                "en": (
                    "Women's tops, shirts, and blouses",
                    "blouse",
                    "shirt",
                    "t-shirt",
                    "top",
                    "tunic",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="trousers-skirt-shorts",
            label="Women's trousers, skirts, and shorts",
            keywords_by_lang={
                "en": (
                    "Women's trousers, skirts, and shorts",
                    "jeans",
                    "leggings",
                    "shorts",
                    "skirt",
                    "slacks",
                    "trousers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="underwear-lingerie",
            label="Women's underwear and lingerie",
            keywords_by_lang={
                "en": (
                    "Women's underwear and lingerie",
                    "bodysuit",
                    "bra",
                    "brassiere",
                    "briefs",
                    "knickers",
                    "lingerie",
                    "panties",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.2.3": (
        SubLabel(
            id="pyjamas-nightshirts-nightdresses-dressing-gowns-bathrobes-et",
            label="pyjamas, nightshirts, nightdresses, dressing gowns, bathrobes, etc.",
            keywords_by_lang={
                "en": (
                    "pyjamas, nightshirts, nightdresses, dressing gowns, bathrobes, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="raincoats-anoraks-parkas-blousons-jackets-trousers-waistcoat",
            label="raincoats, anoraks, parkas, blousons, jackets, trousers, waistcoats, suits, costumes, dresses, skirts, etc.",
            keywords_by_lang={
                "en": (
                    "raincoats, anoraks, parkas, blousons, jackets, trousers, waistcoats, suits, costumes, dresses, skirts, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vests-underpants-socks-stockings-tights-etc",
            label="vests, underpants, socks, stockings, tights, etc.",
            keywords_by_lang={
                "en": ("vests, underpants, socks, stockings, tights, etc.",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="babygrow",
            label="babygrow",
            keywords_by_lang={"auto": ("babygrow",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-dresses-skirts",
            label="Infant dresses and skirts",
            keywords_by_lang={
                "en": (
                    "Infant dresses and skirts",
                    "baby dress",
                    "baby girl outfit",
                    "infant jumper dress",
                    "infant skirt",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-loungewear",
            label="Infant loungewear and robes",
            keywords_by_lang={
                "en": (
                    "Infant loungewear and robes",
                    "baby dressing gown",
                    "baby housecoat",
                    "infant bathrobe",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-outerwear",
            label="Infant outerwear",
            keywords_by_lang={
                "en": (
                    "Infant outerwear",
                    "baby coat",
                    "baby jacket",
                    "baby parka",
                    "infant anorak",
                    "infant blouson",
                    "toddler winter coat",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-sleepwear",
            label="Infant sleepwear",
            keywords_by_lang={
                "en": (
                    "Infant sleepwear",
                    "baby nightshirt",
                    "baby onesie pyjamas",
                    "baby pyjamas",
                    "infant nightdress",
                    "infant sleepsuit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-socks-tights",
            label="Infant socks and tights",
            keywords_by_lang={
                "en": (
                    "Infant socks and tights",
                    "baby booties",
                    "baby socks",
                    "infant stockings",
                    "infant tights",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-trousers-suits",
            label="Infant trousers and suits",
            keywords_by_lang={
                "en": (
                    "Infant trousers and suits",
                    "baby costume",
                    "baby suit",
                    "baby trousers",
                    "infant formal wear",
                    "infant overalls",
                    "infant pants",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-vests-underwear",
            label="Infant vests and underwear",
            keywords_by_lang={
                "en": (
                    "Infant vests and underwear",
                    "baby bodysuit",
                    "baby undershirt",
                    "baby vest",
                    "infant onesie",
                    "infant underpants",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other infant garments",
            keywords_by_lang={"en": ("Other infant garments",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.2.4": (
        SubLabel(
            id="school-uniforms",
            label="school uniforms",
            keywords_by_lang={"en": ("school uniforms",)},
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
        SubLabel(
            id="school-uniform-pe-kit",
            label="PE kit",
            keywords_by_lang={
                "en": (
                    "PE kit",
                    "School PE kit",
                    "school gym kit",
                    "school sports uniform",
                    "sports shirt",
                    "sports shorts",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="school-uniform-blazer",
            label="School blazer",
            keywords_by_lang={
                "en": (
                    "School blazer",
                    "school blazer",
                    "school jacket",
                    "school suit jacket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="school-uniform-bottom",
            label="School uniform bottom",
            keywords_by_lang={
                "en": (
                    "School uniform bottom",
                    "school culottes",
                    "school pinafore",
                    "school shorts",
                    "school skirt",
                    "school trousers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="school-uniform-top",
            label="School uniform top",
            keywords_by_lang={
                "en": (
                    "School uniform top",
                    "school blouse",
                    "school cardigan",
                    "school jumper",
                    "school polo shirt",
                    "school shirt",
                    "school sweater",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.3.1": (
        SubLabel(
            id="ties-handkerchiefs-scarves-gloves-mittens-muffs-belts-braces",
            label="ties, handkerchiefs, scarves, gloves, mittens, muffs, belts, braces, aprons, smocks, bibs, sleeve protectors, hats, caps, berets, bonnets, etc.",
            keywords_by_lang={
                "en": (
                    "ties, handkerchiefs, scarves, gloves, mittens, muffs, belts, braces, aprons, smocks, bibs, sleeve protectors, hats, caps, berets, bonnets, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="working-gloves",
            label="working gloves",
            keywords_by_lang={"en": ("working gloves",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pyjamas",
            label="pyjamas",
            keywords_by_lang={"auto": ("pyjamas",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="socks",
            label="socks",
            keywords_by_lang={"auto": ("socks",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="swimwear",
            label="swimwear",
            keywords_by_lang={"auto": ("swimwear",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tights",
            label="tights",
            keywords_by_lang={"auto": ("tights",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="underwear",
            label="underwear",
            keywords_by_lang={"auto": ("underwear",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="aprons-and-smocks",
            label="Aprons and smocks",
            keywords_by_lang={
                "en": (
                    "Aprons and smocks",
                    "apron",
                    "kitchen apron",
                    "pinafore",
                    "smock",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="baby-bibs",
            label="Baby bibs",
            keywords_by_lang={"en": ("Baby bibs", "bib", "drool bib", "feeding bib")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="belts",
            label="Belts",
            keywords_by_lang={"en": ("Belts", "belt", "leather belt", "waist belt")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="braces-and-suspenders",
            label="Braces and suspenders",
            keywords_by_lang={"en": ("Braces and suspenders", "braces", "suspenders")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gloves-and-mittens",
            label="Gloves and mittens",
            keywords_by_lang={
                "en": (
                    "Gloves and mittens",
                    "gloves",
                    "mittens",
                    "mitts",
                    "winter gloves",
                    "working gloves",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="handkerchiefs",
            label="Handkerchiefs",
            keywords_by_lang={
                "en": ("Handkerchiefs", "handkerchief", "hanky", "pocket square")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hats-and-caps",
            label="Hats and caps",
            keywords_by_lang={
                "en": (
                    "Hats and caps",
                    "baseball cap",
                    "beanie",
                    "beret",
                    "bonnet",
                    "cap",
                    "hat",
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
            id="scarves",
            label="Scarves",
            keywords_by_lang={
                "en": ("Scarves", "neck scarf", "pashmina", "scarf", "shawl", "stole")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="ties-and-cravats",
            label="Ties and cravats",
            keywords_by_lang={
                "en": (
                    "Ties and cravats",
                    "ascot",
                    "bow tie",
                    "cravat",
                    "necktie",
                    "tie",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.3.2": (
        SubLabel(
            id="sewing-threads-knitting-yarns-and-accessories-used-in-the-cr",
            label="sewing threads, knitting yarns and accessories used in the creation of clothing, such as buckles, buttons, press studs, zip fasteners, ribbons, laces, trimmings, etc.",
            keywords_by_lang={
                "en": (
                    "sewing threads, knitting yarns and accessories used in the creation of clothing, such as buckles, buttons, press studs, zip fasteners, ribbons, laces, trimmings, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
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
            id="belt",
            label="belt",
            keywords_by_lang={"auto": ("belt",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hat",
            label="hat",
            keywords_by_lang={"auto": ("hat",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="scarf",
            label="scarf",
            keywords_by_lang={"auto": ("scarf",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="buckles",
            label="Buckles",
            keywords_by_lang={
                "en": (
                    "Buckles",
                    "belt buckles",
                    "buckles",
                    "clothing buckles",
                    "fastening buckles",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="buttons",
            label="Buttons",
            keywords_by_lang={
                "en": (
                    "Buttons",
                    "buttons",
                    "clothing buttons",
                    "sew-on buttons",
                    "shirt buttons",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="knitting-yarn",
            label="Knitting yarn",
            keywords_by_lang={
                "en": (
                    "Knitting yarn",
                    "crochet yarn",
                    "knitting yarn",
                    "skeins of yarn",
                    "wool for knitting",
                    "yarn",
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
            id="ribbons-and-laces",
            label="Ribbons and laces",
            keywords_by_lang={
                "en": (
                    "Ribbons and laces",
                    "clothing laces",
                    "decorative ribbon",
                    "edging trim",
                    "lace trim",
                    "ribbons",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sewing-thread",
            label="Sewing thread",
            keywords_by_lang={
                "en": (
                    "Sewing thread",
                    "hand sewing thread",
                    "machine thread",
                    "sewing cotton",
                    "sewing thread",
                    "thread for sewing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="trimmings",
            label="Trimmings and sewing accessories",
            keywords_by_lang={
                "en": (
                    "Trimmings and sewing accessories",
                    "clothing appliques",
                    "embellishments",
                    "sewing accessories",
                    "sewing notions",
                    "trimmings",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="zippers",
            label="Zippers and fasteners",
            keywords_by_lang={
                "en": (
                    "Zippers and fasteners",
                    "hooks and eyes",
                    "press studs",
                    "slide fasteners",
                    "snap fasteners",
                    "zip fasteners",
                    "zippers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.1.4.1": (
        SubLabel(
            id="dry-cleaning-laundering-and-dyeing-of-garments",
            label="dry-cleaning, laundering and dyeing of garments",
            keywords_by_lang={
                "en": ("dry-cleaning, laundering and dyeing of garments",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dry-cleaning-service",
            label="Dry cleaning",
            keywords_by_lang={
                "en": (
                    "Dry cleaning",
                    "dry cleaners",
                    "dry cleaning service",
                    "garment dry cleaning",
                    "professional dry cleaning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="garment-dyeing",
            label="Garment dyeing",
            keywords_by_lang={
                "en": (
                    "Garment dyeing",
                    "clothing dyeing",
                    "fabric dyeing service",
                    "garment re-dyeing",
                    "textile dyeing service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="laundry-service",
            label="Laundry service",
            keywords_by_lang={
                "en": (
                    "Laundry service",
                    "clothing laundry",
                    "garment washing",
                    "laundering service",
                    "laundry service",
                    "wash and fold",
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
    ),
    "03.1.4.2": (
        SubLabel(
            id="darning-mending-repair-and-altering-of-garments",
            label="darning, mending, repair and altering of garments",
            keywords_by_lang={
                "en": ("darning, mending, repair and altering of garments",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-of-garments",
            label="hire of garments",
            keywords_by_lang={"en": ("hire of garments",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tailoring-services-for-which-the-customer-supplies-the-mater",
            label="tailoring services for which the customer supplies the material",
            keywords_by_lang={
                "en": (
                    "tailoring services for which the customer supplies the material",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="garment-hire",
            label="Clothing hire",
            keywords_by_lang={
                "en": (
                    "Clothing hire",
                    "clothing rental service",
                    "costume hire",
                    "garment rental",
                    "suit hire",
                    "tuxedo rental",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="darning-service",
            label="Darning service",
            keywords_by_lang={
                "en": (
                    "Darning service",
                    "darning",
                    "invisible mending",
                    "knitwear repair",
                    "textile darning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="garment-alteration",
            label="Garment alteration and repair",
            keywords_by_lang={
                "en": (
                    "Garment alteration and repair",
                    "clothing alteration",
                    "clothing mending",
                    "garment repair",
                    "hemming services",
                    "letting out clothing",
                    "taking in clothing",
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
            id="custom-tailoring-service",
            label="Tailoring service",
            keywords_by_lang={
                "en": (
                    "Tailoring service",
                    "bespoke tailoring service",
                    "custom fit service",
                    "custom garment adjustment",
                    "garment fitting",
                    "tailoring services",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.2.1.1": (
        SubLabel(
            id="all-footwear-for-men-either-ready-to-wear-or-made-to-measure",
            label="all footwear for men either ready-to-wear or made-to-measure",
            keywords_by_lang={
                "en": ("all footwear for men either ready-to-wear or made-to-measure",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gaiters-and-similar-articles",
            label="gaiters and similar articles",
            keywords_by_lang={"en": ("gaiters and similar articles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parts-of-footwear-such-as-heels-soles-etc-purchased-by-house",
            label="parts of footwear, such as heels, soles, etc., purchased by households with the intention of undertaking footwear repair themselves",
            keywords_by_lang={
                "en": (
                    "parts of footwear, such as heels, soles, etc., purchased by households with the intention of undertaking footwear repair themselves",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shoelaces",
            label="shoelaces",
            keywords_by_lang={"en": ("shoelaces",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-footwear-suitable-for-everyday-or-leisure-wear-shoes-",
            label="sports footwear suitable for everyday or leisure wear (shoes for jogging, cross-training, tennis, basketball, boating, etc.)",
            keywords_by_lang={
                "en": (
                    "sports footwear suitable for everyday or leisure wear (shoes for jogging, cross-training, tennis, basketball, boating, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-shoes",
            label="mens shoes",
            keywords_by_lang={"auto": ("mens shoes",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mens-trainers",
            label="mens trainers",
            keywords_by_lang={"auto": ("mens trainers",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="men-boots",
            label="Boots for men",
            keywords_by_lang={
                "en": (
                    "Boots for men",
                    "ankle boots",
                    "boots",
                    "chelsea boots",
                    "leather boots",
                    "work boots",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="men-shoes-casual",
            label="Casual shoes for men",
            keywords_by_lang={
                "en": (
                    "Casual shoes for men",
                    "casual shoes",
                    "everyday shoes",
                    "lifestyle sneakers",
                    "loafers",
                    "mens sneakers",
                    "slip-ons",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="footwear-parts-accessories",
            label="Footwear parts and accessories for men",
            keywords_by_lang={
                "en": (
                    "Footwear parts and accessories for men",
                    "boot laces",
                    "gaiters",
                    "replacement heels",
                    "shoe heels",
                    "shoe soles",
                    "shoelaces",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="men-formal-shoes",
            label="Formal shoes for men",
            keywords_by_lang={
                "en": (
                    "Formal shoes for men",
                    "brogues",
                    "derby shoes",
                    "dress shoes",
                    "formal shoes",
                    "oxford shoes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other", "Other footwear products for men")},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="men-sandals",
            label="Sandals and flip-flops for men",
            keywords_by_lang={
                "en": (
                    "Sandals and flip-flops for men",
                    "beach sandals",
                    "flip-flops",
                    "sandals",
                    "slides",
                    "thongs",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="men-sports-shoes-leisure",
            label="Sports shoes for leisure wear for men",
            keywords_by_lang={
                "en": (
                    "Sports shoes for leisure wear for men",
                    "athletic leisure shoes",
                    "basketball shoes",
                    "cross-training shoes",
                    "jogging shoes",
                    "running shoes",
                    "tennis shoes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.2.1.2": (
        SubLabel(
            id="all-footwear-for-women-either-ready-to-wear-or-made-to-measu",
            label="all footwear for women either ready-to-wear or made to measure",
            keywords_by_lang={
                "en": (
                    "all footwear for women either ready-to-wear or made to measure",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gaiters-and-similar-articles",
            label="gaiters and similar articles",
            keywords_by_lang={"en": ("gaiters and similar articles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parts-of-footwear-such-as-heels-soles-etc-purchased-by-house",
            label="parts of footwear, such as heels, soles, etc., purchased by households with the intention of undertaking footwear repair themselves",
            keywords_by_lang={
                "en": (
                    "parts of footwear, such as heels, soles, etc., purchased by households with the intention of undertaking footwear repair themselves",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shoelaces",
            label="shoelaces",
            keywords_by_lang={"en": ("shoelaces", "Shoelaces", "laces", "shoe laces")},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-footwear-suitable-for-everyday-or-leisure-wear-shoes-",
            label="sports footwear suitable for everyday or leisure wear (shoes for jogging, cross-training, tennis, basketball, boating, etc.)",
            keywords_by_lang={
                "en": (
                    "sports footwear suitable for everyday or leisure wear (shoes for jogging, cross-training, tennis, basketball, boating, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-sandals",
            label="womens sandals",
            keywords_by_lang={"auto": ("womens sandals",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-shoes",
            label="womens shoes",
            keywords_by_lang={"auto": ("womens shoes",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="womens-trainers",
            label="womens trainers",
            keywords_by_lang={"auto": ("womens trainers",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="women-shoes-casual",
            label="Casual women's shoes",
            keywords_by_lang={
                "en": (
                    "Casual women's shoes",
                    "everyday shoes",
                    "flats",
                    "loafers",
                    "slip-ons",
                    "walking shoes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="footwear-repair-parts",
            label="Footwear repair parts",
            keywords_by_lang={
                "en": (
                    "Footwear repair parts",
                    "heel replacements",
                    "shoe heels",
                    "shoe repair kits",
                    "shoe soles",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gaiters",
            label="Gaiters",
            keywords_by_lang={
                "en": ("Gaiters", "hiking gaiters", "leg covers", "leggings gaiters")
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
            id="women-boots",
            label="Women's boots",
            keywords_by_lang={
                "en": (
                    "Women's boots",
                    "ankle boots",
                    "booties",
                    "knee-high boots",
                    "winter boots",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="women-heels",
            label="Women's heels",
            keywords_by_lang={
                "en": (
                    "Women's heels",
                    "dress shoes",
                    "evening shoes",
                    "high heels",
                    "pumps",
                    "stiletto heels",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="women-sports-footwear",
            label="Women's leisure sports footwear",
            keywords_by_lang={
                "en": (
                    "Women's leisure sports footwear",
                    "basketball shoes",
                    "boat shoes",
                    "cross-training shoes",
                    "tennis shoes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="women-sandals",
            label="Women's sandals",
            keywords_by_lang={
                "en": (
                    "Women's sandals",
                    "flip-flops",
                    "slides",
                    "strappy sandals",
                    "thong sandals",
                    "wedges",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="women-sneakers",
            label="Women's sneakers",
            keywords_by_lang={
                "en": (
                    "Women's sneakers",
                    "casual sneakers",
                    "fashion sneakers",
                    "jogging shoes",
                    "leisure sports shoes",
                    "trainers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "03.2.1.3": (
        SubLabel(
            id="all-footwear-for-infants-and-children-under-13-years-of-age-",
            label="all footwear for infants and children (under 13 years of age) either ready-to-wear or made to measure",
            keywords_by_lang={
                "en": (
                    "all footwear for infants and children (under 13 years of age) either ready-to-wear or made to measure",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="baby-s-booties-made-of-fabric-or-sheepskin",
            label="baby’s booties made of fabric or sheepskin",
            keywords_by_lang={"en": ("baby’s booties made of fabric or sheepskin",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gaiters-and-similar-articles",
            label="gaiters and similar articles",
            keywords_by_lang={"en": ("gaiters and similar articles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parts-of-footwear-such-as-heels-soles-etc-purchased-by-house",
            label="parts of footwear, such as heels, soles, etc., purchased by households with the intention of repairing footwear themselves",
            keywords_by_lang={
                "en": (
                    "parts of footwear, such as heels, soles, etc., purchased by households with the intention of repairing footwear themselves",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shoelaces",
            label="shoelaces",
            keywords_by_lang={
                "en": (
                    "shoelaces",
                    "Shoelaces",
                    "laces",
                    "shoe strings",
                    "sneaker laces",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-footwear-suitable-for-everyday-or-leisure-wear-shoes-",
            label="sports footwear suitable for everyday or leisure wear (shoes for jogging cross-training, tennis, basketball, boating, etc.)",
            keywords_by_lang={
                "en": (
                    "sports footwear suitable for everyday or leisure wear (shoes for jogging cross-training, tennis, basketball, boating, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-shoes",
            label="childrens shoes",
            keywords_by_lang={"auto": ("childrens shoes",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-trainers",
            label="childrens trainers",
            keywords_by_lang={"auto": ("childrens trainers",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-boots",
            label="Children's boots",
            keywords_by_lang={
                "en": (
                    "Children's boots",
                    "children's ankle boots",
                    "fashion boots for children",
                    "kids boots",
                    "toddler boots",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-shoes-casual",
            label="Children's casual shoes",
            keywords_by_lang={
                "en": (
                    "Children's casual shoes",
                    "casual shoes for kids",
                    "children's loafers",
                    "everyday children's footwear",
                    "kids flats",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-sandals",
            label="Children's sandals",
            keywords_by_lang={
                "en": (
                    "Children's sandals",
                    "children's flip flops",
                    "kids sandals",
                    "sandals for infants",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-sneakers",
            label="Children's sneakers",
            keywords_by_lang={
                "en": (
                    "Children's sneakers",
                    "children's athletic shoes",
                    "kids jogging shoes",
                    "kids trainers",
                    "tennis shoes for children",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="footwear-parts",
            label="Footwear repair parts",
            keywords_by_lang={
                "en": (
                    "Footwear repair parts",
                    "diy shoe repair parts",
                    "replacement heels",
                    "shoe soles",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gaiters",
            label="Gaiters",
            keywords_by_lang={
                "en": (
                    "Gaiters",
                    "children's gaiters",
                    "leggings gaiters",
                    "shoe covers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="infant-booties",
            label="Infant booties",
            keywords_by_lang={
                "en": (
                    "Infant booties",
                    "baby booties",
                    "crib shoes",
                    "infant fabric shoes",
                    "soft sole baby shoes",
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
    ),
    "03.2.2.0": (
        SubLabel(
            id="dyeing-of-shoes",
            label="dyeing of shoes",
            keywords_by_lang={"en": ("dyeing of shoes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-of-footwear",
            label="hire of footwear",
            keywords_by_lang={"en": ("hire of footwear",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-footwear",
            label="repair of footwear",
            keywords_by_lang={"en": ("repair of footwear",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shoe-cleaning-services",
            label="shoe-cleaning services",
            keywords_by_lang={"en": ("shoe-cleaning services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shoe-hire",
            label="Footwear hire",
            keywords_by_lang={
                "en": (
                    "Footwear hire",
                    "footwear rental service",
                    "shoe hire service",
                    "shoe rental",
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
            id="shoe-cleaning-service",
            label="Shoe cleaning service",
            keywords_by_lang={
                "en": (
                    "Shoe cleaning service",
                    "boot cleaning",
                    "shoe cleaning",
                    "shoe polishing service",
                    "shoe shine",
                    "sneaker cleaning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="shoe-dyeing-service",
            label="Shoe dyeing service",
            keywords_by_lang={
                "en": (
                    "Shoe dyeing service",
                    "custom shoe tinting",
                    "footwear coloring service",
                    "shoe dyeing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="shoe-repair-service",
            label="Shoe repair service",
            keywords_by_lang={
                "en": (
                    "Shoe repair service",
                    "boot repair",
                    "cobbler service",
                    "heel repair",
                    "resole service",
                    "shoe repair",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
}
