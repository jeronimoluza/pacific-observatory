"""Auto-generated sub_labels for COICOP class 02.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "02.1.1.0": (
        SubLabel(
            id="aperitifs-other-than-wine-based-aperitifs",
            label="aperitifs, other than wine-based aperitifs",
            keywords_by_lang={"en": ("aperitifs, other than wine-based aperitifs",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="eaux-de-vie-liqueurs-and-other-spirits-with-a-high-alcohol-c",
            label="eaux de vie, liqueurs and other spirits with a high alcohol content",
            keywords_by_lang={
                "en": (
                    "eaux de vie, liqueurs and other spirits with a high alcohol content",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mead",
            label="mead",
            keywords_by_lang={"en": ("mead", "Mead", "honey wine", "metheglin")},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pomace-brandies-such-as-pisco-grappa-and-marc",
            label="pomace brandies, such as pisco, grappa and marc",
            keywords_by_lang={
                "en": ("pomace brandies, such as pisco, grappa and marc",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-spirit",
            label="other spirit",
            keywords_by_lang={"auto": ("other spirit",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="aperitif-spirit",
            label="Aperitif (spirit-based)",
            keywords_by_lang={
                "en": (
                    "Aperitif (spirit-based)",
                    "absinthe",
                    "aperitif",
                    "bitters",
                    "ouzo",
                    "pastis",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="brandy",
            label="Brandy",
            keywords_by_lang={
                "en": ("Brandy", "armagnac", "brandy", "brandy de jerez", "cognac")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="eaux-de-vie",
            label="Eaux de vie",
            keywords_by_lang={
                "en": (
                    "Eaux de vie",
                    "eau de vie",
                    "fruit brandy",
                    "schnaps",
                    "slivovitz",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gin",
            label="Gin",
            keywords_by_lang={
                "en": ("Gin", "dry gin", "gin", "jenever", "london dry gin")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="liqueur",
            label="Liqueur",
            keywords_by_lang={
                "en": ("Liqueur", "cordial", "creme liqueur", "liqueur", "schnapps")
            },
            allowed_bases=frozenset({"item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other", "Other spirits and liquors")},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pomace-brandy",
            label="Pomace brandy",
            keywords_by_lang={
                "en": ("Pomace brandy", "bagaceira", "grappa", "marc", "pisco")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="rum",
            label="Rum",
            keywords_by_lang={
                "en": (
                    "Rum",
                    "dark rum",
                    "rhum agricole",
                    "rum",
                    "spiced rum",
                    "white rum",
                )
            },
            allowed_bases=frozenset({"volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tequila",
            label="Tequila",
            keywords_by_lang={
                "en": (
                    "Tequila",
                    "añejo tequila",
                    "blanco tequila",
                    "mezcal",
                    "reposado tequila",
                    "tequila",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vodka",
            label="Vodka",
            keywords_by_lang={"en": ("Vodka", "grain spirit", "vodka")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="whisky",
            label="Whisky",
            keywords_by_lang={
                "en": (
                    "Whisky",
                    "bourbon",
                    "rye whiskey",
                    "scotch",
                    "single malt",
                    "whiskey",
                )
            },
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.1.2.1": (
        SubLabel(
            id="champagne-and-other-sparkling-wines-from-grapes",
            label="champagne and other sparkling wines from grapes",
            keywords_by_lang={
                "en": ("champagne and other sparkling wines from grapes",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fortified-wines-such-as-vermouth-sherry-and-port-wine",
            label="fortified wines, such as vermouth, sherry and port wine",
            keywords_by_lang={
                "en": ("fortified wines, such as vermouth, sherry and port wine",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ice-wine",
            label="ice wine",
            keywords_by_lang={"en": ("ice wine",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="low-alcohol-and-non-alcoholic-wine",
            label="low-alcohol and non-alcoholic wine",
            keywords_by_lang={"en": ("low-alcohol and non-alcoholic wine",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wine-from-grapes",
            label="wine from grapes",
            keywords_by_lang={"en": ("wine from grapes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wine-based-aperitifs",
            label="wine-based aperitifs",
            keywords_by_lang={"en": ("wine-based aperitifs",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="red-wine",
            label="red wine",
            keywords_by_lang={"auto": ("red wine",)},
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="white-wine",
            label="white wine",
            keywords_by_lang={"auto": ("white wine",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dessert-wine",
            label="Dessert wine",
            keywords_by_lang={
                "en": (
                    "Dessert wine",
                    "dessert wine",
                    "ice wine",
                    "late harvest wine",
                    "sauternes",
                    "vin santo",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fortified-wine",
            label="Fortified wine",
            keywords_by_lang={
                "en": (
                    "Fortified wine",
                    "fortified wine",
                    "madeira",
                    "marsala",
                    "port wine",
                    "sherry",
                    "vermouth",
                )
            },
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="non-alcoholic-wine",
            label="Non-alcoholic wine",
            keywords_by_lang={
                "en": (
                    "Non-alcoholic wine",
                    "alcohol-free wine",
                    "dealcoholized wine",
                    "low-alcohol wine",
                    "non-alcoholic wine",
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
            id="sparkling-wine",
            label="Sparkling wine",
            keywords_by_lang={
                "en": (
                    "Sparkling wine",
                    "cava",
                    "champagne",
                    "fizz",
                    "prosecco",
                    "sparkling wine",
                    "spumante",
                )
            },
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="table-wine",
            label="Table wine",
            keywords_by_lang={
                "en": (
                    "Table wine",
                    "grape wine",
                    "red wine",
                    "rosé wine",
                    "table wine",
                    "white wine",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wine-aperitif",
            label="Wine-based aperitif",
            keywords_by_lang={
                "en": (
                    "Wine-based aperitif",
                    "aperitif wine",
                    "aromatized wine",
                    "wine cocktail",
                    "wine-based aperitif",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.1.2.2": (
        SubLabel(
            id="ciders-and-perries-including-sake",
            label="ciders and perries, including sake",
            keywords_by_lang={"en": ("ciders and perries, including sake",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cider",
            label="Cider",
            keywords_by_lang={
                "en": ("Cider", "apple cider", "cidre", "hard cider", "sparkling cider")
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
            id="perry",
            label="Perry",
            keywords_by_lang={"en": ("Perry", "pear cider", "perry cider", "poiré")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sake",
            label="Sake",
            keywords_by_lang={
                "en": (
                    "Sake",
                    "daiginjo sake",
                    "ginjo sake",
                    "junmai sake",
                    "nihonshu",
                    "rice wine",
                )
            },
            allowed_bases=frozenset({"volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.1.3.0": (
        SubLabel(
            id="all-kinds-of-beers-such-as-ale-lager-stout-and-porter",
            label="all kinds of beers, such as ale, lager, stout and porter",
            keywords_by_lang={
                "en": ("all kinds of beers, such as ale, lager, stout and porter",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="low-alcohol-beer-and-non-alcoholic-beer",
            label="low-alcohol beer and non-alcoholic beer",
            keywords_by_lang={"en": ("low-alcohol beer and non-alcoholic beer",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-alcoholic-beer",
            label="0.0 beer",
            keywords_by_lang={
                "en": (
                    "0.0 beer",
                    "Non-alcoholic beer",
                    "alcohol-free beer",
                    "na beer",
                    "non-alcoholic beer",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="ale",
            label="Ale",
            keywords_by_lang={
                "en": ("Ale", "ale", "bitter", "india pale ale", "ipa", "pale ale")
            },
            allowed_bases=frozenset({"volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="craft-beer",
            label="Craft beer",
            keywords_by_lang={
                "en": ("Craft beer", "artisan beer", "craft beer", "microbrewery beer")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lager",
            label="Lager",
            keywords_by_lang={
                "en": ("Lager", "blonde ale", "helles", "lager", "pilsner")
            },
            allowed_bases=frozenset({"item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="low-alcohol-beer",
            label="Low-alcohol beer",
            keywords_by_lang={
                "en": (
                    "Low-alcohol beer",
                    "light beer",
                    "low-ABV beer",
                    "low-alcohol beer",
                    "session beer",
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
            id="stout",
            label="Stout and porter",
            keywords_by_lang={
                "en": ("Stout and porter", "imperial stout", "porter", "stout")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wheat-beer",
            label="Wheat beer",
            keywords_by_lang={
                "en": ("Wheat beer", "hefeweizen", "weissbier", "wheat beer", "witbier")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.1.9.0": (
        SubLabel(
            id="mixed-alcohol-based-drinks-such-as-soda-water-and-mineral-wa",
            label="mixed alcohol-based drinks, such as soda water and mineral water-based mixed alcoholic drinks (alcopops)",
            keywords_by_lang={
                "en": (
                    "mixed alcohol-based drinks, such as soda water and mineral water-based mixed alcoholic drinks (alcopops)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shandy-cola-beer-and-radler",
            label="shandy, cola beer and radler",
            keywords_by_lang={"en": ("shandy, cola beer and radler",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="alcopop",
            label="alcopop",
            keywords_by_lang={"auto": ("alcopop",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="alcopops",
            label="Alcopops",
            keywords_by_lang={
                "en": (
                    "Alcopops",
                    "RTD",
                    "alcoholic soda",
                    "alcopop",
                    "cooler",
                    "malt beverage",
                    "ready-to-drink alcoholic beverage",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cola-beer",
            label="Cola beer",
            keywords_by_lang={
                "en": ("Cola beer", "beer-cola mix", "cola beer", "diesel beer")
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
            id="shandy",
            label="Shandy",
            keywords_by_lang={
                "en": ("Shandy", "beer-lemonade mix", "panaché", "radler", "shandy")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.2.0.0": (
        SubLabel(
            id="ageing-and-bottling-services",
            label="ageing and bottling services",
            keywords_by_lang={"en": ("ageing and bottling services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="brewing-services",
            label="brewing services",
            keywords_by_lang={"en": ("brewing services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="distilling-and-fermentation-services",
            label="distilling and fermentation services",
            keywords_by_lang={"en": ("distilling and fermentation services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fruit-and-vegetable-crushing-and-pressing-services-for-the-p",
            label="fruit and vegetable crushing and pressing services for the production of alcoholic beverages",
            keywords_by_lang={
                "en": (
                    "fruit and vegetable crushing and pressing services for the production of alcoholic beverages",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ageing-bottling-service",
            label="Ageing and bottling services",
            keywords_by_lang={
                "en": (
                    "Ageing and bottling services",
                    "beverage bottling service",
                    "bottling service",
                    "cask ageing service",
                    "wine ageing service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="brewing-service",
            label="Brewing services",
            keywords_by_lang={
                "en": (
                    "Brewing services",
                    "beer brewing service",
                    "brewery service",
                    "craft brewing service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="distilling-fermentation-service",
            label="Distilling and fermentation services",
            keywords_by_lang={
                "en": (
                    "Distilling and fermentation services",
                    "distillation service",
                    "fermentation service",
                    "home brewing fermentation service",
                    "home distillation service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="crushing-pressing-service",
            label="Fruit and vegetable crushing and pressing services",
            keywords_by_lang={
                "en": (
                    "Fruit and vegetable crushing and pressing services",
                    "cider pressing service",
                    "fruit crushing service",
                    "must extraction service",
                    "vegetable pressing service",
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
    "02.3.0.1": (
        SubLabel(
            id="cigarettes",
            label="cigarettes",
            keywords_by_lang={"en": ("cigarettes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cigarettes-that-are-purchased-in-bars-and-restaurants-provid",
            label="cigarettes that are purchased in bars and restaurants, provided that a service charge is not applied",
            keywords_by_lang={
                "en": (
                    "cigarettes that are purchased in bars and restaurants, provided that a service charge is not applied",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cigarettes-carton",
            label="Cigarettes (carton)",
            keywords_by_lang={
                "en": (
                    "Cigarettes (carton)",
                    "bulk cigarettes",
                    "carton of cigarettes",
                    "cigarette carton",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cigarettes-pack",
            label="Cigarettes (pack)",
            keywords_by_lang={
                "en": (
                    "Cigarettes (pack)",
                    "cigarettes",
                    "ciggs",
                    "pack of cigarettes",
                    "smoke",
                    "tobacco cigarettes",
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
    "02.3.0.2": (
        SubLabel(
            id="cigar",
            label="Cigar",
            keywords_by_lang={
                "en": (
                    "Cigar",
                    "cigar",
                    "cigarillo",
                    "hand-rolled cigar",
                    "premium cigar",
                    "stogie",
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
    "02.3.0.9": (
        SubLabel(
            id="cigarette-papers-and-single-use-filters-which-are-consumed-w",
            label="cigarette papers and single-use filters which are consumed with the cigarette",
            keywords_by_lang={
                "en": (
                    "cigarette papers and single-use filters which are consumed with the cigarette",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cigarette-tobacco-and-tobacco-leaf",
            label="cigarette tobacco and tobacco leaf",
            keywords_by_lang={"en": ("cigarette tobacco and tobacco leaf",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pipe-tobacco-chewing-tobacco-hookah-blends-snus-and-snuff",
            label="pipe tobacco, chewing tobacco, hookah blends, snus and snuff",
            keywords_by_lang={
                "en": ("pipe tobacco, chewing tobacco, hookah blends, snus and snuff",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="refills-for-electronic-cigarettes-with-or-without-nicotine",
            label="refills for electronic cigarettes, with or without nicotine",
            keywords_by_lang={
                "en": ("refills for electronic cigarettes, with or without nicotine",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tobacco-that-is-consumed-with-a-shisha-or-a-hookah-pipe-if-c",
            label="tobacco that is consumed with a shisha or a hookah pipe if consumed at home",
            keywords_by_lang={
                "en": (
                    "tobacco that is consumed with a shisha or a hookah pipe if consumed at home",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="chewing-tobacco",
            label="Chewing tobacco",
            keywords_by_lang={
                "en": ("Chewing tobacco", "chew", "chewing tobacco", "dip", "snuff")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cigarette-papers-filters",
            label="Cigarette papers and filters",
            keywords_by_lang={
                "en": (
                    "Cigarette papers and filters",
                    "cigarette filters",
                    "cigarette tips",
                    "filter tips",
                    "rolling papers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="e-cigarette-refill",
            label="E-cigarette refills",
            keywords_by_lang={
                "en": (
                    "E-cigarette refills",
                    "e-liquid",
                    "nicotine e-liquid",
                    "vape juice",
                    "vape pods",
                    "vape refill",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hookah-shisha-tobacco",
            label="Hookah/Shisha tobacco",
            keywords_by_lang={
                "en": (
                    "Hookah/Shisha tobacco",
                    "argileh tobacco",
                    "hookah blend",
                    "hookah tobacco",
                    "shisha molasses",
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
            id="pipe-tobacco",
            label="Pipe tobacco",
            keywords_by_lang={
                "en": ("Pipe tobacco", "loose leaf tobacco", "pipe tobacco")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="rolling-tobacco",
            label="RYO tobacco",
            keywords_by_lang={
                "en": (
                    "RYO tobacco",
                    "Rolling tobacco",
                    "cigarette tobacco",
                    "loose tobacco for rolling",
                    "roll-your-own tobacco",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="snus",
            label="Snus",
            keywords_by_lang={
                "en": ("Snus", "moist snuff", "nicotine pouches", "snus")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "02.4.0.0": (
        SubLabel(
            id="marijuana-opium-cocaine-and-their-derivatives",
            label="marijuana, opium, cocaine and their derivatives",
            keywords_by_lang={
                "en": ("marijuana, opium, cocaine and their derivatives",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-narcotics-including-chemicals-and-synthetic-drugs",
            label="other narcotics, including chemicals and synthetic drugs",
            keywords_by_lang={
                "en": ("other narcotics, including chemicals and synthetic drugs",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-vegetable-based-narcotics-such-as-betel-leaves-betel-n",
            label="other vegetable-based narcotics, such as betel leaves, betel nuts, cola nuts, kava, khat, and psilocybin mushroom",
            keywords_by_lang={
                "en": (
                    "other vegetable-based narcotics, such as betel leaves, betel nuts, cola nuts, kava, khat, and psilocybin mushroom",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="betel-products",
            label="Betel products",
            keywords_by_lang={
                "en": ("Betel products", "areca nut", "betel leaves", "betel nuts")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cannabis-products",
            label="Cannabis products",
            keywords_by_lang={
                "en": (
                    "Cannabis products",
                    "cannabis",
                    "ganja",
                    "marijuana",
                    "pot",
                    "weed",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cocaine-and-derivatives",
            label="Cocaine and derivatives",
            keywords_by_lang={
                "en": ("Cocaine and derivatives", "cocaine", "coke", "crack")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hallucinogenic-mushrooms",
            label="Hallucinogenic mushrooms",
            keywords_by_lang={
                "en": (
                    "Hallucinogenic mushrooms",
                    "magic mushrooms",
                    "psilocybin mushrooms",
                    "shrooms",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="kava",
            label="Kava",
            keywords_by_lang={"en": ("Kava", "kava-kava", "piper methysticum")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="khat-leaves",
            label="Khat leaves",
            keywords_by_lang={"en": ("Khat leaves", "gat", "khat", "qat")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="opium-and-derivatives",
            label="Opium and derivatives",
            keywords_by_lang={
                "en": ("Opium and derivatives", "opium", "poppy-based-narcotics")
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
            id="stimulant-nuts",
            label="Stimulant nuts",
            keywords_by_lang={"en": ("Stimulant nuts", "cola nuts", "kola nuts")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="synthetic-drugs",
            label="Synthetic drugs",
            keywords_by_lang={
                "en": (
                    "Synthetic drugs",
                    "designer drugs",
                    "research chemicals",
                    "synthetic chemicals",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
}
