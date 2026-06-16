"""Auto-generated sub_labels for COICOP class 05.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "05.1.1.1": (
        SubLabel(
            id="beds-mattresses-mattress-bases-tatamis-wardrobes-and-bedside",
            label="beds, mattresses, mattress bases (tatamis), wardrobes and bedside tables",
            keywords_by_lang={
                "en": (
                    "beds, mattresses, mattress bases (tatamis), wardrobes and bedside tables",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bunk-beds-and-baby-furniture-such-as-cradles-high-chairs-and",
            label="bunk beds and baby furniture, such as cradles, high chairs and playpens",
            keywords_by_lang={
                "en": (
                    "bunk beds and baby furniture, such as cradles, high chairs and playpens",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="furniture-primarily-for-bathroom-use",
            label="furniture primarily for bathroom use",
            keywords_by_lang={"en": ("furniture primarily for bathroom use",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="inflatable-sofas-armchairs-and-beds",
            label="inflatable sofas, armchairs and beds",
            keywords_by_lang={"en": ("inflatable sofas, armchairs and beds",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-tables-chairs-cupboards-and-surfaces",
            label="kitchen tables, chairs, cupboards and surfaces",
            keywords_by_lang={
                "en": ("kitchen tables, chairs, cupboards and surfaces",)
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pieces-of-custom-made-furniture",
            label="pieces of custom-made furniture",
            keywords_by_lang={"en": ("pieces of custom-made furniture",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sofas-couches-tables-chairs-cupboards-chests-of-drawers-book",
            label="sofas, couches, tables, chairs, cupboards, chests of drawers, bookshelves, hanger stands and coat stands",
            keywords_by_lang={
                "en": (
                    "sofas, couches, tables, chairs, cupboards, chests of drawers, bookshelves, hanger stands and coat stands",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bed",
            label="bed",
            keywords_by_lang={"auto": ("bed",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="clothes-shoe-rack",
            label="clothes shoe rack",
            keywords_by_lang={"auto": ("clothes shoe rack",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="desk",
            label="desk",
            keywords_by_lang={"auto": ("desk",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dining-table",
            label="dining table",
            keywords_by_lang={"auto": ("dining table",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="floor-chair-recliner",
            label="floor chair recliner",
            keywords_by_lang={"auto": ("floor chair recliner",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="furniture-cushion",
            label="furniture cushion",
            keywords_by_lang={"auto": ("furniture cushion",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="office-chair",
            label="office chair",
            keywords_by_lang={"auto": ("office chair",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="side-table-stand",
            label="side table stand",
            keywords_by_lang={"auto": ("side table stand",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sofa",
            label="sofa",
            keywords_by_lang={"auto": ("sofa",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="storage-cabinet",
            label="storage cabinet",
            keywords_by_lang={"auto": ("storage cabinet",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tv-stand",
            label="tv stand",
            keywords_by_lang={"auto": ("tv stand",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="armchair",
            label="Armchairs",
            keywords_by_lang={
                "en": (
                    "Armchairs",
                    "accent chair",
                    "armchair",
                    "easy chair",
                    "inflatable armchair",
                    "recliner",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="baby-furniture",
            label="Baby furniture",
            keywords_by_lang={
                "en": (
                    "Baby furniture",
                    "bassinet",
                    "cot",
                    "cradle",
                    "crib",
                    "high chair",
                    "playpen",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bathroom-furniture",
            label="Bathroom furniture",
            keywords_by_lang={
                "en": (
                    "Bathroom furniture",
                    "bathroom cabinet",
                    "bathroom shelving",
                    "under-sink cabinet",
                    "vanity unit",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bed-frame",
            label="Bed frames and bases",
            keywords_by_lang={
                "en": (
                    "Bed frames and bases",
                    "bed base",
                    "bed frame",
                    "bedstead",
                    "mattress base",
                    "tatami base",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bookshelf-storage",
            label="Bookshelves and storage units",
            keywords_by_lang={
                "en": (
                    "Bookshelves and storage units",
                    "bookcase",
                    "bookshelf",
                    "display cabinet",
                    "shelving unit",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="chair",
            label="Chairs",
            keywords_by_lang={
                "en": (
                    "Chairs",
                    "accent chair",
                    "chair",
                    "dining chair",
                    "kitchen chair",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="chest-of-drawers",
            label="Chests of drawers",
            keywords_by_lang={
                "en": (
                    "Chests of drawers",
                    "bureau",
                    "chest of drawers",
                    "commode",
                    "dresser",
                    "sideboard",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hanger-coat-stand",
            label="Hanger and coat stands",
            keywords_by_lang={
                "en": (
                    "Hanger and coat stands",
                    "coat hanger stand",
                    "coat rack",
                    "coat stand",
                    "hall tree",
                    "hat stand",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mattress",
            label="Mattresses",
            keywords_by_lang={
                "en": (
                    "Mattresses",
                    "air mattress",
                    "foam mattress",
                    "inflatable bed",
                    "mattress",
                    "spring mattress",
                )
            },
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
            id="sofa-couch",
            label="Sofas and couches",
            keywords_by_lang={
                "en": (
                    "Sofas and couches",
                    "couch",
                    "davenport",
                    "inflatable sofa",
                    "loveseat",
                    "settee",
                    "sofa",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="table",
            label="Tables",
            keywords_by_lang={
                "en": (
                    "Tables",
                    "coffee table",
                    "console table",
                    "dining table",
                    "end table",
                    "side table",
                    "table",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wardrobe-cupboard",
            label="Wardrobes and cupboards",
            keywords_by_lang={
                "en": (
                    "Wardrobes and cupboards",
                    "armoire",
                    "closet unit",
                    "cupboard",
                    "storage cabinet",
                    "wardrobe",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "05.1.1.2": (
        SubLabel(
            id="camping-furniture",
            label="camping furniture",
            keywords_by_lang={"en": ("camping furniture",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="custom-made-furniture",
            label="custom-made furniture",
            keywords_by_lang={"en": ("custom-made furniture",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="furniture-used-primarily-in-gardens",
            label="furniture used primarily in gardens",
            keywords_by_lang={"en": ("furniture used primarily in gardens",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="small-garden-sheds-for-the-storage-of-garden-tools-and-machi",
            label="small garden sheds for the storage of garden tools and machines",
            keywords_by_lang={
                "en": (
                    "small garden sheds for the storage of garden tools and machines",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wrought-iron-benches-tables-and-arbours",
            label="wrought iron benches, tables and arbours",
            keywords_by_lang={"en": ("wrought iron benches, tables and arbours",)},
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
    "05.1.1.3": (
        SubLabel(
            id="lighting-equipment-such-as-ceiling-lights-standard-lamps-glo",
            label="lighting equipment, such as ceiling lights, standard lamps, globe lights, bedside lamps, light and LED strings, and parts thereof",
            keywords_by_lang={
                "en": (
                    "lighting equipment, such as ceiling lights, standard lamps, globe lights, bedside lamps, light and LED strings, and parts thereof",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ceiling-light",
            label="ceiling light",
            keywords_by_lang={"auto": ("ceiling light",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="light-bulb",
            label="light bulb",
            keywords_by_lang={"auto": ("light bulb",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="table-lamp",
            label="table lamp",
            keywords_by_lang={"auto": ("table lamp",)},
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
    "05.1.1.4": (
        SubLabel(
            id="leather-and-fur-for-upholstery-and-room-decoration",
            label="leather and fur for upholstery and room decoration",
            keywords_by_lang={
                "en": ("leather and fur for upholstery and room decoration",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="loose-carpets-and-rugs",
            label="loose carpets and rugs",
            keywords_by_lang={"en": ("loose carpets and rugs",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pictures-sculptures-engravings-tapestries-and-other-art-obje",
            label="pictures, sculptures, engravings, tapestries and other art objects, including reproductions of works of art and other ornaments",
            keywords_by_lang={
                "en": (
                    "pictures, sculptures, engravings, tapestries and other art objects, including reproductions of works of art and other ornaments",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="screens-folding-partitions-non-textile-blinds-mirrors-candle",
            label="screens, folding partitions, non-textile blinds, mirrors, candle holders and candlesticks",
            keywords_by_lang={
                "en": (
                    "screens, folding partitions, non-textile blinds, mirrors, candle holders and candlesticks",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="statuettes-and-other-decorative-articles-including-those-mad",
            label="statuettes and other decorative articles, including those made of porcelain and crystal glass",
            keywords_by_lang={
                "en": (
                    "statuettes and other decorative articles, including those made of porcelain and crystal glass",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wall-clocks-floor-clocks-alarm-clocks-and-travel-clocks",
            label="wall clocks, floor clocks, alarm clocks and travel clocks",
            keywords_by_lang={
                "en": ("wall clocks, floor clocks, alarm clocks and travel clocks",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="blinds",
            label="blinds",
            keywords_by_lang={"auto": ("blinds",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="rug",
            label="rug",
            keywords_by_lang={"auto": ("rug",)},
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
    "05.1.2.0": (
        SubLabel(
            id="hire-of-furniture-garden-and-camping-furniture-furnishings-a",
            label="hire of furniture, garden and camping furniture, furnishings and loose carpets",
            keywords_by_lang={
                "en": (
                    "hire of furniture, garden and camping furniture, furnishings and loose carpets",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="installation-of-furniture-when-separately-priced",
            label="installation of furniture, when separately priced",
            keywords_by_lang={
                "en": ("installation of furniture, when separately priced",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-furniture-garden-and-camping-furniture-furnishings",
            label="repair of furniture, garden and camping furniture, furnishings and loose carpets",
            keywords_by_lang={
                "en": (
                    "repair of furniture, garden and camping furniture, furnishings and loose carpets",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="restoration-of-works-of-art-antique-furniture-and-antique-fl",
            label="restoration of works of art, antique furniture and antique floor coverings other than those acquired primarily as stores of value (capital formation)",
            keywords_by_lang={
                "en": (
                    "restoration of works of art, antique furniture and antique floor coverings other than those acquired primarily as stores of value (capital formation)",
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
    "05.2.1.1": (
        SubLabel(
            id="furnishing-fabrics-curtain-material-curtains-double-curtains",
            label="furnishing fabrics, curtain material, curtains, double curtains, awnings, door curtains and fabric blinds",
            keywords_by_lang={
                "en": (
                    "furnishing fabrics, curtain material, curtains, double curtains, awnings, door curtains and fabric blinds",
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
    "05.2.1.2": (
        SubLabel(
            id="bed-linen-such-as-sheets-pillowcases-blankets-travelling-rug",
            label="bed linen, such as sheets, pillowcases, blankets, travelling rugs, plaids, eiderdowns, counterpanes and mosquito nets",
            keywords_by_lang={
                "en": (
                    "bed linen, such as sheets, pillowcases, blankets, travelling rugs, plaids, eiderdowns, counterpanes and mosquito nets",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bedding-such-as-covers-for-futons-pillows-bolsters-and-hammo",
            label="bedding, such as covers for futons, pillows, bolsters and hammocks",
            keywords_by_lang={
                "en": (
                    "bedding, such as covers for futons, pillows, bolsters and hammocks",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bed-protector-pad",
            label="bed protector pad",
            keywords_by_lang={"auto": ("bed protector pad",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bedsheet",
            label="bedsheet",
            keywords_by_lang={"auto": ("bedsheet",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="duet-cover",
            label="duet cover",
            keywords_by_lang={"auto": ("duet cover",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="duvet",
            label="duvet",
            keywords_by_lang={"auto": ("duvet",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="duvet-cover",
            label="duvet cover",
            keywords_by_lang={"auto": ("duvet cover",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pillow",
            label="pillow",
            keywords_by_lang={"auto": ("pillow",)},
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
    "05.2.1.3": (
        SubLabel(
            id="table-and-bathroom-linen-such-as-tablecloths-table-napkins-t",
            label="table and bathroom linen, such as tablecloths, table napkins, towels and face cloths",
            keywords_by_lang={
                "en": (
                    "table and bathroom linen, such as tablecloths, table napkins, towels and face cloths",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-towel-textile",
            label="kitchen towel textile",
            keywords_by_lang={"auto": ("kitchen towel textile",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="towel",
            label="towel",
            keywords_by_lang={"auto": ("towel",)},
            allowed_bases=frozenset({"count", "item"}),
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
    "05.2.1.9": (
        SubLabel(
            id="bathroom-mats-rush-mats-and-doormats",
            label="bathroom mats, rush mats and doormats",
            keywords_by_lang={"en": ("bathroom mats, rush mats and doormats",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="feathers-and-other-fillers-for-pillows",
            label="feathers and other fillers for pillows",
            keywords_by_lang={"en": ("feathers and other fillers for pillows",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="oilcloth",
            label="oilcloth",
            keywords_by_lang={"en": ("oilcloth",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="textile-shopping-bags-laundry-bags-shoe-bags-covers-for-clot",
            label="textile shopping bags, laundry bags, shoe bags, covers for clothes and furniture, flags, sunshades, etc.",
            keywords_by_lang={
                "en": (
                    "textile shopping bags, laundry bags, shoe bags, covers for clothes and furniture, flags, sunshades, etc.",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="absorbent-mat",
            label="absorbent mat",
            keywords_by_lang={"auto": ("absorbent mat",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bath-mat",
            label="bath mat",
            keywords_by_lang={"auto": ("bath mat",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="blanket",
            label="blanket",
            keywords_by_lang={"auto": ("blanket",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cushion",
            label="cushion",
            keywords_by_lang={"auto": ("cushion",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="door-curtain",
            label="door curtain",
            keywords_by_lang={"auto": ("door curtain",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mattress-topper",
            label="mattress topper",
            keywords_by_lang={"auto": ("mattress topper",)},
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
    "05.2.2.0": (
        SubLabel(
            id="hire-of-household-textiles",
            label="hire of household textiles",
            keywords_by_lang={"en": ("hire of household textiles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-household-textiles",
            label="repair of household textiles",
            keywords_by_lang={"en": ("repair of household textiles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sewing-of-household-textiles",
            label="sewing of household textiles",
            keywords_by_lang={"en": ("sewing of household textiles",)},
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
    "05.3.1.1": (
        SubLabel(
            id="dishwashers",
            label="dishwashers",
            keywords_by_lang={"en": ("dishwashers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-gas-oil-ceramic-and-induction-panels-hobs-spit-roas",
            label="electric, gas, oil, ceramic and induction panels; hobs; spit roasters; electric. gas and convection ovens; and combined cooker and microwave ovens",
            keywords_by_lang={
                "en": (
                    "electric, gas, oil, ceramic and induction panels; hobs; spit roasters; electric. gas and convection ovens; and combined cooker and microwave ovens",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="extractor-hoods",
            label="extractor hoods",
            keywords_by_lang={"en": ("extractor hoods",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="refrigerators-dual-temperature-refrigerators-and-freezers",
            label="refrigerators, dual-temperature refrigerators and freezers",
            keywords_by_lang={
                "en": ("refrigerators, dual-temperature refrigerators and freezers",)
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
    "05.3.1.2": (
        SubLabel(
            id="ironing-machines-and-electric-mangles",
            label="ironing machines and electric mangles",
            keywords_by_lang={"en": ("ironing machines and electric mangles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="washing-machines-dryers-drum-dryers-drying-cabinets-and-dryi",
            label="washing machines, dryers, drum dryers, drying cabinets and drying radiators",
            keywords_by_lang={
                "en": (
                    "washing machines, dryers, drum dryers, drying cabinets and drying radiators",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="washing-machine",
            label="washing machine",
            keywords_by_lang={"auto": ("washing machine",)},
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
    "05.3.1.3": (
        SubLabel(
            id="air-conditioners-humidifiers-space-heaters-water-heaters-and",
            label="air conditioners, humidifiers, space heaters, water heaters and ventilators",
            keywords_by_lang={
                "en": (
                    "air conditioners, humidifiers, space heaters, water heaters and ventilators",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="air-conditioner",
            label="air conditioner",
            keywords_by_lang={"auto": ("air conditioner",)},
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-heater",
            label="electric heater",
            keywords_by_lang={"auto": ("electric heater",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fan",
            label="fan",
            keywords_by_lang={"auto": ("fan",)},
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
    "05.3.1.4": (
        SubLabel(
            id="vacuum-cleaners-steam-cleaning-machines-carpet-shampooing-ma",
            label="vacuum cleaners; steam-cleaning machines; carpet shampooing machines; and machines for scrubbing, waxing and polishing floors",
            keywords_by_lang={
                "en": (
                    "vacuum cleaners; steam-cleaning machines; carpet shampooing machines; and machines for scrubbing, waxing and polishing floors",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vacuum-cleaner",
            label="vacuum cleaner",
            keywords_by_lang={"auto": ("vacuum cleaner",)},
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
    "05.3.1.9": (
        SubLabel(
            id="other-major-household-appliances-such-as-safes-sewing-machin",
            label="other major household appliances, such as safes, sewing machines, knitting machines and water softeners",
            keywords_by_lang={
                "en": (
                    "other major household appliances, such as safes, sewing machines, knitting machines and water softeners",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-cooking-pot",
            label="electric cooking pot",
            keywords_by_lang={"auto": ("electric cooking pot",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-scale",
            label="kitchen scale",
            keywords_by_lang={"auto": ("kitchen scale",)},
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
    "05.3.2.1": (
        SubLabel(
            id="can-openers",
            label="can openers",
            keywords_by_lang={"en": ("can openers",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="deep-fryers",
            label="deep fryers",
            keywords_by_lang={"en": ("deep fryers",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-knives",
            label="electric knives",
            keywords_by_lang={"en": ("electric knives",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hot-plates",
            label="hot plates",
            keywords_by_lang={"en": ("hot plates",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ice-cream-makers",
            label="ice cream makers",
            keywords_by_lang={"en": ("ice cream makers",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="meat-and-fish-grills",
            label="meat and fish grills",
            keywords_by_lang={"en": ("meat and fish grills",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="multifunction-machines-food-mixers-blenders-and-blenders-wit",
            label="multifunction machines, food mixers, blenders and blenders with heating elements",
            keywords_by_lang={
                "en": (
                    "multifunction machines, food mixers, blenders and blenders with heating elements",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-electric-appliances-for-the-cooking-and-processing-of-fo",
            label="non-electric appliances for the cooking and processing of food, such as purée makers, mincers, hot plates and household scales",
            keywords_by_lang={
                "en": (
                    "non-electric appliances for the cooking and processing of food, such as purée makers, mincers, hot plates and household scales",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rice-cookers-and-slow-cookers",
            label="rice cookers and slow cookers",
            keywords_by_lang={"en": ("rice cookers and slow cookers",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sandwich-grills",
            label="sandwich grills",
            keywords_by_lang={"en": ("sandwich grills",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="slicing-machines",
            label="slicing machines",
            keywords_by_lang={"en": ("slicing machines",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sorbet-makers",
            label="sorbet makers",
            keywords_by_lang={"en": ("sorbet makers",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toasters",
            label="toasters",
            keywords_by_lang={"en": ("toasters",)},
            allowed_bases=frozenset({"item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="yoghurt-makers",
            label="yoghurt makers",
            keywords_by_lang={"en": ("yoghurt makers",)},
            allowed_bases=frozenset({"item"}),
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
    "05.3.2.2": (
        SubLabel(
            id="coffee-machines",
            label="coffee machines",
            keywords_by_lang={"en": ("coffee machines",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="coffee-mills",
            label="coffee mills",
            keywords_by_lang={"en": ("coffee mills",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="juice-extractors",
            label="juice extractors",
            keywords_by_lang={"en": ("juice extractors",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="kettles",
            label="kettles",
            keywords_by_lang={"en": ("kettles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-electric-appliances-for-the-preparation-of-beverages-suc",
            label="non-electric appliances for the preparation of beverages, such as coffee mills, sparkling- water makers and juice extractors",
            keywords_by_lang={
                "en": (
                    "non-electric appliances for the preparation of beverages, such as coffee mills, sparkling- water makers and juice extractors",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sparkling-water-makers",
            label="sparkling water makers",
            keywords_by_lang={"en": ("sparkling water makers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tea-makers",
            label="tea makers",
            keywords_by_lang={"en": ("tea makers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="water-boilers",
            label="water boilers",
            keywords_by_lang={"en": ("water boilers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="coffee-machine",
            label="coffee machine",
            keywords_by_lang={"auto": ("coffee machine",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="kettle",
            label="kettle",
            keywords_by_lang={"auto": ("kettle",)},
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
    "05.3.2.9": (
        SubLabel(
            id="electric-blankets",
            label="electric blankets",
            keywords_by_lang={"en": ("electric blankets",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-irons",
            label="electric irons",
            keywords_by_lang={"en": ("electric irons",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fans",
            label="fans",
            keywords_by_lang={"en": ("fans",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-non-electric-household-appliances",
            label="other non-electric household appliances",
            keywords_by_lang={"en": ("other non-electric household appliances",)},
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
    "05.3.3.0": (
        SubLabel(
            id="hire-of-household-appliances",
            label="hire of household appliances",
            keywords_by_lang={"en": ("hire of household appliances",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="installation-of-household-appliances-if-priced-separately",
            label="installation of household appliances (if priced separately)",
            keywords_by_lang={
                "en": ("installation of household appliances (if priced separately)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-household-appliances",
            label="repair of household appliances",
            keywords_by_lang={"en": ("repair of household appliances",)},
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
    "05.4.0.1": (
        SubLabel(
            id="glassware-crystal-ware-ceramic-ware-and-china-ware-of-the-ki",
            label="glassware, crystal ware, ceramic ware and china ware of the kind used for table, kitchen, bathroom or toilet",
            keywords_by_lang={
                "en": (
                    "glassware, crystal ware, ceramic ware and china ware of the kind used for table, kitchen, bathroom or toilet",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="glasses",
            label="glasses",
            keywords_by_lang={"auto": ("glasses",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="plates",
            label="plates",
            keywords_by_lang={"auto": ("plates",)},
            allowed_bases=frozenset({"count", "item"}),
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
    "05.4.0.2": (
        SubLabel(
            id="cutlery-flatware-and-silverware",
            label="cutlery, flatware and silverware",
            keywords_by_lang={"en": ("cutlery, flatware and silverware",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cutlery",
            label="cutlery",
            keywords_by_lang={"auto": ("cutlery",)},
            allowed_bases=frozenset({"count", "item"}),
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
    "05.4.0.3": (
        SubLabel(
            id="household-articles-of-all-materials-such-as-containers-for-b",
            label="household articles of all materials, such as containers for bread, coffee, spices and so on, waste bins, waste-paper baskets, laundry baskets, portable money boxes and strongboxes, towel rails, bottle racks, letter boxes, feeding bottles, thermos flasks and iceboxes",
            keywords_by_lang={
                "en": (
                    "household articles of all materials, such as containers for bread, coffee, spices and so on, waste bins, waste-paper baskets, laundry baskets, portable money boxes and strongboxes, towel rails, bottle racks, letter boxes, feeding bottles, thermos flasks and iceboxes",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-utensils-of-all-materials-such-as-saucepans-stewpots",
            label="kitchen utensils of all materials, such as saucepans, stewpots, pressure cookers and frying pans;",
            keywords_by_lang={
                "en": (
                    "kitchen utensils of all materials, such as saucepans, stewpots, pressure cookers and frying pans;",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="food-storage",
            label="food storage",
            keywords_by_lang={"auto": ("food storage",)},
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-utensils",
            label="kitchen utensils",
            keywords_by_lang={"auto": ("kitchen utensils",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pots-and-pans",
            label="pots and pans",
            keywords_by_lang={"auto": ("pots and pans",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="chopping-board",
            label="Chopping Board",
            keywords_by_lang={
                "en": ("Chopping Board", "chopping block", "cutting board")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="feeding-bottle",
            label="Feeding Bottle",
            keywords_by_lang={
                "en": ("Feeding Bottle", "baby bottle", "nursing bottle")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="food-storage-container",
            label="Food Storage Container",
            keywords_by_lang={
                "en": ("Food Storage Container", "bread bin", "canister", "spice jar")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="frying-pan",
            label="Frying Pan",
            keywords_by_lang={"en": ("Frying Pan", "fry pan", "skillet", "wok")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="laundry-basket",
            label="Laundry Basket",
            keywords_by_lang={
                "en": ("Laundry Basket", "clothes basket", "laundry hamper")
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
            id="pressure-cooker",
            label="Pressure Cooker",
            keywords_by_lang={"en": ("Pressure Cooker", "canner")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="saucepan",
            label="Saucepan",
            keywords_by_lang={"en": ("Saucepan", "mini pans", "pot", "stewpot")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="thermos-flask",
            label="Thermos Flask",
            keywords_by_lang={
                "en": ("Thermos Flask", "icebox", "insulated bottle", "vacuum flask")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="waste-bin",
            label="Waste Bin",
            keywords_by_lang={
                "en": ("Waste Bin", "garbage bin", "trash can", "waste-paper basket")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "05.4.0.4": (
        SubLabel(
            id="repair-and-hire-of-glassware-crystal-ware-ceramic-ware-and-c",
            label="repair and hire of glassware, crystal ware, ceramic ware and china ware; cutlery, flatware and silverware; and kitchen utensils and articles",
            keywords_by_lang={
                "en": (
                    "repair and hire of glassware, crystal ware, ceramic ware and china ware; cutlery, flatware and silverware; and kitchen utensils and articles",
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
    "05.5.1.0": (
        SubLabel(
            id="electric-drills-percussion-drill-electric-saws-electric-sand",
            label="electric drills, percussion drill, electric saws, electric sanders",
            keywords_by_lang={
                "en": (
                    "electric drills, percussion drill, electric saws, electric sanders",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-screwdrivers",
            label="electric screwdrivers",
            keywords_by_lang={"en": ("electric screwdrivers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="garden-tractors-chain-saws-lawn-mowers-clipper-for-lawn-hedg",
            label="garden tractors, chain saws, lawn mowers, clipper for lawn, hedge cutters, cultivators",
            keywords_by_lang={
                "en": (
                    "garden tractors, chain saws, lawn mowers, clipper for lawn, hedge cutters, cultivators",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="water-pumps",
            label="water pumps",
            keywords_by_lang={"en": ("water pumps",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="power-tools",
            label="power tools",
            keywords_by_lang={"auto": ("power tools",)},
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
    "05.5.2.1": (
        SubLabel(
            id="ladders-and-steps",
            label="ladders and steps",
            keywords_by_lang={"en": ("ladders and steps",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="power-shears-wheelbarrows-watering-cans-hoses-spades-shovels",
            label="power shears, wheelbarrows, watering cans, hoses, spades, shovels, rakes, forks, scythes, sickles and secateurs",
            keywords_by_lang={
                "en": (
                    "power shears, wheelbarrows, watering cans, hoses, spades, shovels, rakes, forks, scythes, sickles and secateurs",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="saws-hammers-screwdriver-wrenches-spanners-pliers-trimming-k",
            label="saws, hammers, screwdriver, wrenches, spanners, pliers, trimming knives, rasps and files;",
            keywords_by_lang={
                "en": (
                    "saws, hammers, screwdriver, wrenches, spanners, pliers, trimming knives, rasps and files;",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hand-tools",
            label="hand tools",
            keywords_by_lang={"auto": ("hand tools",)},
            allowed_bases=frozenset({"count", "item"}),
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
    "05.5.2.2": (
        SubLabel(
            id="fittings-for-radiators-and-fireplaces-other-miscellaneous-ac",
            label="fittings for radiators and fireplaces, other miscellaneous accessories for the house (curtain rails, curtain rods of wood or plastics, string curtain rods, carpet rods, hooks, etc.) or for the garden (chains, grids, stakes and hoop segments for fencing and bordering)",
            keywords_by_lang={
                "en": (
                    "fittings for radiators and fireplaces, other miscellaneous accessories for the house (curtain rails, curtain rods of wood or plastics, string curtain rods, carpet rods, hooks, etc.) or for the garden (chains, grids, stakes and hoop segments for fencing and bordering)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="small-electric-accessories-such-as-lamp-bulbs-fluorescent-li",
            label="small electric accessories, such as lamp bulbs, fluorescent lighting tubes, torches, flashlights, hand lamps, electric accessories as fuses, and electric batteries and chargers for general use",
            keywords_by_lang={
                "en": (
                    "small electric accessories, such as lamp bulbs, fluorescent lighting tubes, torches, flashlights, hand lamps, electric accessories as fuses, and electric batteries and chargers for general use",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tool-accessories",
            label="tool accessories",
            keywords_by_lang={"auto": ("tool accessories",)},
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
    "05.5.3.0": (
        SubLabel(
            id="repair-and-hire-of-motorized-tools-and-equipment",
            label="repair and hire of motorized tools and equipment",
            keywords_by_lang={
                "en": ("repair and hire of motorized tools and equipment",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-and-hire-of-non-motorized-small-tools-and-miscellaneo",
            label="repair and hire of non-motorized small tools and miscellaneous accessories",
            keywords_by_lang={
                "en": (
                    "repair and hire of non-motorized small tools and miscellaneous accessories",
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
    "05.6.1.1": (
        SubLabel(
            id="cloths-floor-cloths-and-chamois-leathers",
            label="cloths, floor cloths and chamois leathers",
            keywords_by_lang={"en": ("cloths, floor cloths and chamois leathers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="detergents-hand-and-machine-dishwashing-detergent-scouring-p",
            label="detergents, hand and machine dishwashing detergent, scouring powders, disinfectant bleaches, softeners, conditioners and stain removers",
            keywords_by_lang={
                "en": (
                    "detergents, hand and machine dishwashing detergent, scouring powders, disinfectant bleaches, softeners, conditioners and stain removers",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dish-brushes-household-sponges-scourers-and-steel-wool",
            label="dish brushes, household sponges, scourers and steel wool",
            keywords_by_lang={
                "en": ("dish brushes, household sponges, scourers and steel wool",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dustpans-dusting-brushes-and-dusters",
            label="dustpans, dusting brushes and dusters",
            keywords_by_lang={"en": ("dustpans, dusting brushes and dusters",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="floor-waxes-and-polishes",
            label="floor waxes and polishes",
            keywords_by_lang={"en": ("floor waxes and polishes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="general-purpose-cleansers-window-cleaning-products-unblockin",
            label="general-purpose cleansers, window-cleaning products, unblocking agents and disinfectants",
            keywords_by_lang={
                "en": (
                    "general-purpose cleansers, window-cleaning products, unblocking agents and disinfectants",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="polishes-creams-and-other-shoe-cleaning-items-e-g-shoe-brush",
            label="polishes, creams and other shoe-cleaning items (e.g., shoe brushes)",
            keywords_by_lang={
                "en": (
                    "polishes, creams and other shoe-cleaning items (e.g., shoe brushes)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pool-cleaning-chemicals-and-water-treatment-chemicals",
            label="pool cleaning chemicals and water treatment chemicals",
            keywords_by_lang={
                "en": ("pool cleaning chemicals and water treatment chemicals",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vacuum-cleaner-bags",
            label="vacuum cleaner bags",
            keywords_by_lang={
                "en": (
                    "vacuum cleaner bags",
                    "Vacuum Cleaner Bags",
                    "dust bag",
                    "vacuum filter",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bleach",
            label="bleach",
            keywords_by_lang={"auto": ("bleach",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dishwasher-tablets",
            label="dishwasher tablets",
            keywords_by_lang={"auto": ("dishwasher tablets",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fabric-conditioner",
            label="fabric conditioner",
            keywords_by_lang={"auto": ("fabric conditioner",)},
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="floor-cleaner",
            label="floor cleaner",
            keywords_by_lang={"auto": ("floor cleaner",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="surface-cleaner",
            label="surface cleaner",
            keywords_by_lang={"auto": ("surface cleaner",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toilet-cleaner",
            label="toilet cleaner",
            keywords_by_lang={"auto": ("toilet cleaner",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bleach-and-disinfectant",
            label="Bleach and Disinfectant",
            keywords_by_lang={
                "en": (
                    "Bleach and Disinfectant",
                    "chlorine bleach",
                    "disinfecting solution",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="brushes-and-dusting-tools",
            label="Brushes and Dusting Tools",
            keywords_by_lang={
                "en": (
                    "Brushes and Dusting Tools",
                    "dish brush",
                    "dusting brush",
                    "dustpan",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cleaning-cloths-and-sponges",
            label="Cleaning Cloths and Sponges",
            keywords_by_lang={
                "en": (
                    "Cleaning Cloths and Sponges",
                    "microfiber cloth",
                    "scouring pad",
                    "steel wool",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dishwashing-detergent",
            label="Dishwashing Detergent",
            keywords_by_lang={
                "en": (
                    "Dishwashing Detergent",
                    "dish pods",
                    "dish soap",
                    "dishwasher tablets",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fabric-softener",
            label="Fabric Softener",
            keywords_by_lang={
                "en": (
                    "Fabric Softener",
                    "laundry conditioner",
                    "scent booster",
                    "softener liquid",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="floor-and-surface-polish",
            label="Floor and Surface Polish",
            keywords_by_lang={
                "en": (
                    "Floor and Surface Polish",
                    "floor wax",
                    "furniture polish",
                    "shine spray",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="general-purpose-cleaner",
            label="General Purpose Cleaner",
            keywords_by_lang={
                "en": (
                    "General Purpose Cleaner",
                    "bath cleaner",
                    "multi-surface cleaner",
                    "surface spray",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="laundry-detergent",
            label="Laundry Detergent",
            keywords_by_lang={
                "en": (
                    "Laundry Detergent",
                    "fabric detergent",
                    "laundry soap",
                    "washing liquid",
                )
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
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
    "05.6.1.9": (
        SubLabel(
            id="candles-lamp-wicks-methylated-spirits-plastic-bags-and-garba",
            label="candles, lamp wicks, methylated spirits, plastic bags and garbage bags",
            keywords_by_lang={
                "en": (
                    "candles, lamp wicks, methylated spirits, plastic bags and garbage bags",
                )
            },
            allowed_bases=frozenset({"item", "count", "volume", "mass"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="disposable-plates-cups-and-cutlery",
            label="disposable plates, cups and cutlery",
            keywords_by_lang={"en": ("disposable plates, cups and cutlery",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="filters-tablecloths-and-table-napkins-kitchen-papers-baking-",
            label="filters, tablecloths and table napkins, kitchen papers, baking parchment rolls, kitchen film, aluminium foils and doilies",
            keywords_by_lang={
                "en": (
                    "filters, tablecloths and table napkins, kitchen papers, baking parchment rolls, kitchen film, aluminium foils and doilies",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="insecticides-pesticides-fungicides-and-distilled-water",
            label="insecticides, pesticides, fungicides and distilled water",
            keywords_by_lang={
                "en": ("insecticides, pesticides, fungicides and distilled water",)
            },
            allowed_bases=frozenset({"item", "count", "volume", "mass"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="matches-clothes-pegs-clothes-hangers-pins-safety-pins-sewing",
            label="matches, clothes pegs, clothes hangers, pins, safety pins, sewing needles, knitting needles, thimbles, nails, screws, nuts and bolts, tacks, washers, glues and adhesive tapes for household use, string, twine. rubber gloves and gardening gloves",
            keywords_by_lang={
                "en": (
                    "matches, clothes pegs, clothes hangers, pins, safety pins, sewing needles, knitting needles, thimbles, nails, screws, nuts and bolts, tacks, washers, glues and adhesive tapes for household use, string, twine. rubber gloves and gardening gloves",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="absorbent-mat",
            label="absorbent mat",
            keywords_by_lang={"auto": ("absorbent mat",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="air-freshener-deodorizer",
            label="air freshener deodorizer",
            keywords_by_lang={"auto": ("air freshener deodorizer",)},
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bin-liners",
            label="bin liners",
            keywords_by_lang={"auto": ("bin liners",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="candles",
            label="candles",
            keywords_by_lang={"auto": ("candles",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cleaning-wipes",
            label="cleaning wipes",
            keywords_by_lang={"auto": ("cleaning wipes",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="decorative-stickers-magnets",
            label="decorative stickers magnets",
            keywords_by_lang={"auto": ("decorative stickers magnets",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="disposable-food-packaging",
            label="disposable food packaging",
            keywords_by_lang={"auto": ("disposable food packaging",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="household-filters-drain-covers",
            label="household filters drain covers",
            keywords_by_lang={"auto": ("household filters drain covers",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="household-storage",
            label="household storage",
            keywords_by_lang={"auto": ("household storage",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="insect-control",
            label="insect control",
            keywords_by_lang={"auto": ("insect control",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="kitchen-roll",
            label="kitchen roll",
            keywords_by_lang={"auto": ("kitchen roll",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="moisture-absorber",
            label="moisture absorber",
            keywords_by_lang={"auto": ("moisture absorber",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toilet-paper",
            label="toilet paper",
            keywords_by_lang={"auto": ("toilet paper",)},
            allowed_bases=frozenset({"count", "item"}),
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
    "05.6.2.1": (
        SubLabel(
            id="domestic-services-provided-by-paid-staff-employed-by-the-hou",
            label="domestic services provided by paid staff employed by the household, such as butlers, cooks, maids, drivers, gardeners, governesses, au pairs and nannies",
            keywords_by_lang={
                "en": (
                    "domestic services provided by paid staff employed by the household, such as butlers, cooks, maids, drivers, gardeners, governesses, au pairs and nannies",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ironing-of-household-clothes-and-linen-by-housemaids-in-the-",
            label="ironing of household clothes and linen by housemaids in the family residence",
            keywords_by_lang={
                "en": (
                    "ironing of household clothes and linen by housemaids in the family residence",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="similar-domestic-services-including-babysitting-gardening-an",
            label="similar domestic services including babysitting, gardening and cleaning supplied by enterprises and self-employed persons",
            keywords_by_lang={
                "en": (
                    "similar domestic services including babysitting, gardening and cleaning supplied by enterprises and self-employed persons",
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
    "05.6.2.9": (
        SubLabel(
            id="carpet-cleaning",
            label="carpet cleaning",
            keywords_by_lang={"en": ("carpet cleaning",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dry-cleaning-of-household-linen-and-textiles",
            label="dry-cleaning of household linen and textiles",
            keywords_by_lang={"en": ("dry-cleaning of household linen and textiles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="laundering-and-dyeing-of-household-textiles",
            label="laundering and dyeing of household textiles",
            keywords_by_lang={"en": ("laundering and dyeing of household textiles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-household-services-n-e-c",
            label="other household services n.e.c",
            keywords_by_lang={"en": ("other household services n.e.c",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pest-extermination-and-disinfection",
            label="pest extermination and disinfection",
            keywords_by_lang={"en": ("pest extermination and disinfection",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="taking-care-of-a-dwelling-in-the-absence-of-the-owner-whethe",
            label="taking care of a dwelling in the absence of the owner, whether or not occupying the dwelling; house-sitting",
            keywords_by_lang={
                "en": (
                    "taking care of a dwelling in the absence of the owner, whether or not occupying the dwelling; house-sitting",
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
}
