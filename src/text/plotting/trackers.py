"""Policy-tracker variants sharing the workbook -> addon -> dashboard pipeline.

Each tracker is one crisis lens over the same six regional workbooks and the
same closed v6 (Category, Subcategory) taxonomy. ``fuel`` is the original and
stays the default so existing commands and filenames are unchanged.

A tracker also declares which keyword groups its EPU/Topics tabs display.
Definitions live once in ``src/text/analysis/keywords/{lang}/{family}/`` — one
file per theme — and every build computes every theme. A tracker selects from
that shared result, so two trackers naming the same group are guaranteed to be
showing the same number.

``themes`` takes whole theme files. ``extra_topics`` / ``extra_actors``
cherry-pick individual groups from other themes, for the macro context a lens
wants alongside its own subject.

``topics_chip_groups`` is optional and orders the pill list into collapsible
sections. A tracker that omits it renders one flat list, which is what every
tracker did before the pill list grew to the full sixty-seven groups.

``topics_scope`` is ``"universe"`` for every lens whose subject is one slice of
a shared picture, and ``"tracker"`` for one whose subject *is* a taxonomy. See
the comment on the ``development`` entry.

Adding a tracker is one entry here plus a ``{theme}.json`` per family.
"""

from __future__ import annotations

from pathlib import Path

# The Topics tab deliberately shows the whole 67-group universe, not the
# tracker's own eighteen -- a food index of 150 means nothing until you can see
# governance sitting at 300. Sixty-seven pills in one row is a wall, so they are
# sectioned. The sections are the same for every tracker, because the universe
# is; only which ones open by default differs, and each tracker opens the ones
# its lens exists to show. The rest stay one click away rather than one scroll
# away.
_LEGACY_SECTIONS = [
    (
        "Food & Agriculture",
        [
            "food_prices",
            "food_shortage_rationing",
            "food_security",
            "staple_crops",
            "agricultural_inputs",
            "crop_livestock_shocks",
            "fisheries",
            "food_reserves",
            "food_trade_supply",
        ],
    ),
    (
        "Climate & Environment",
        [
            "el_nino",
            "drought_water",
            "extreme_weather_disaster",
            "climate_environment",
        ],
    ),
    (
        "Hunger, Poverty & Social",
        [
            "hunger_malnutrition",
            "food_assistance",
            "poverty",
            "inequality",
            "health",
            "education",
            "gender_equality",
        ],
    ),
    (
        "Macro & Prices",
        [
            "economic_growth",
            "inflation_prices",
            "external_shocks",
            "trade",
            "fiscal_policy",
            "monetary_policy",
            "public_debt",
            "exchange_rate",
            "financial_stability",
            "capital_flows",
        ],
    ),
    (
        "Energy & Fuel",
        [
            "energy",
            "oil",
            "gasoline",
            "diesel",
            "natural_gas",
            "fuel_rationing",
        ],
    ),
    (
        "Governance & Shocks",
        [
            "political_stability",
            "corruption_governance",
            "armed_conflicts",
            "covid_pandemic",
            "us_china_trade_war",
            "labor_market",
            "housing_real_estate",
            "infrastructure",
        ],
    ),
]

# The development-issues taxonomy: twenty-three broad buckets covering the
# whole development agenda, deliberately coarser than the groups above and
# overlapping them. Sectioned by the World Bank verticals the taxonomy
# itself uses, so the split is the author's rather than ours. On the food and
# fuel lenses every one of these sections is collapsed: they are context for a
# lens, never the lens itself. The ``development`` lens is the inverse -- there
# they are the whole picture and the legacy groups are not shown at all.
_DEV_SECTIONS = [
    (
        "People",
        [
            "dev_health_nutrition",
            "dev_education_skills",
            "dev_labor_social_protection",
            "dev_gender_inclusion",
        ],
    ),
    (
        "Prosperity",
        [
            "dev_macro_growth",
            "dev_inflation_cost_of_living",
            "dev_fiscal_public_finance",
            "dev_monetary_financial",
            "dev_trade_private_sector",
            "dev_poverty_inequality",
        ],
    ),
    (
        "Planet",
        [
            "dev_food_security",
            "dev_agriculture_rural",
            "dev_climate_environment",
            "dev_disasters_resilience",
            "dev_water_sanitation",
        ],
    ),
    (
        "Infrastructure",
        [
            "dev_energy_extractives",
            "dev_transport_urban",
        ],
    ),
    (
        "Digital",
        [
            "dev_digital_technology",
        ],
    ),
    (
        "Cross-Cutting",
        [
            "dev_governance_justice",
            "dev_fragility_conflict",
            "dev_migration_demography",
            "dev_shocks_uncertainty",
            "dev_statistics_monitoring",
        ],
    ),
]

_TOPIC_SECTIONS = _LEGACY_SECTIONS + _DEV_SECTIONS


def _topic_chip_groups(expanded: set[str], sections: list | None = None) -> list[dict]:
    """The topic pills as collapsible sections, opening ``expanded``.

    ``sections`` defaults to the whole 67-group universe. A lens that shows one
    taxonomy on its own passes that taxonomy's sections instead.
    """
    return [
        {"label": label, "expanded": label in expanded, "topics": list(topics)}
        for label, topics in (_TOPIC_SECTIONS if sections is None else sections)
    ]


TRACKERS = {
    "fuel": {
        "slug": "fuel",
        "label": "Fuel Crisis Policy",
        "out_subdir": "fuel",
        "file_suffix": "fuel",
        "aria_subject": "fuel-crisis",
        "subdir": "",
        "themes": ["core", "development"],
        "extra_topics": [],
        "extra_actors": [],
        "topics_chip_groups": _topic_chip_groups({"Energy & Fuel", "Macro & Prices"}),
    },
    "food": {
        "slug": "food_security",
        "label": "Food Security Policy",
        "out_subdir": "food_security",
        "file_suffix": "foodsec",
        "aria_subject": "food-security",
        "subdir": "food_security",
        "themes": ["food", "climate", "development"],
        # Macro context shown beside the food themes. These resolve to the
        # canonical `core` definitions, so `inflation_prices` means the same
        # thing here as it does on the fuel dashboard.
        "extra_topics": [
            "climate_environment",
            "economic_growth",
            "external_shocks",
            "inflation_prices",
            "poverty",
            "trade",
        ],
        "extra_actors": [
            "finance_ministry",
            "government",
            "multilateral_development_bank",
            "world_bank",
        ],
        "topics_chip_groups": _topic_chip_groups(
            {"Food & Agriculture", "Climate & Environment"}
        ),
    },
    # The development-issues taxonomy on its own. The other two lenses show it
    # as context beside the legacy groups, which is where it stops being
    # readable: `food_security` and `dev_food_security` are two different
    # measurements of the same words sitting one pill apart, and in EAP the
    # eleven-term legacy group reads roughly six times its sixty-six-term twin
    # with nothing on screen to say why. This lens drops the legacy side so the
    # taxonomy can be read as the author wrote it.
    #
    # It owns no policy data. `out_subdir` and `subdir` point at the fuel lens
    # so it reuses that addon and workbook unchanged -- the variable here is
    # which topics the Topics tab shows, not which policies it tracks -- and
    # `file_suffix` is what keeps the two dashboards apart in the directory
    # they share.
    "development": {
        "slug": "development",
        "label": "Development Issues",
        "out_subdir": "fuel",
        "file_suffix": "dev",
        "aria_subject": "development-issues",
        "subdir": "",
        # EAP only. `topics/development.json` is translated for the EAP
        # languages and for no others, so outside EAP all twenty-three buckets
        # fall back to English terms and read a fraction of the truth. That is
        # not a thin series, it is a wrong one, and publishing it would look
        # like a measurement.
        "regions": ["eap"],
        "themes": ["development"],
        "extra_topics": [],
        # `development` defines topics but no actors of its own, and the
        # institutions are orthogonal to the taxonomy: the same ministries and
        # lenders appear whichever bucket a story sits in.
        "extra_actors": [
            "imf",
            "world_bank",
            "multilateral_development_bank",
            "central_bank",
            "finance_ministry",
            "government",
            "parliament",
            "courts_judiciary",
            "commercial_banks",
            "credit_rating_agency",
            "international_investors",
            "international_organizations",
            "state_owned_enterprises",
            "labor_unions",
            "military_security",
            "us_government",
            "china_government",
        ],
        # The only lens that hard-filters its Topics tab. Everywhere else the
        # tracker slice is a default focus and the full universe stays one click
        # away; here showing the legacy groups at all is the ambiguity this lens
        # exists to remove.
        "topics_scope": "tracker",
        "topics_chip_groups": _topic_chip_groups(
            {label for label, _ in _DEV_SECTIONS}, _DEV_SECTIONS
        ),
    },
}

DEFAULT_TRACKER = "fuel"


def get_tracker(name: str | None) -> dict:
    key = (name or DEFAULT_TRACKER).lower()
    if key not in TRACKERS:
        raise ValueError(
            f"Unknown tracker '{name}'. Available: {', '.join(sorted(TRACKERS))}"
        )
    return TRACKERS[key]


ADDON_SUFFIX = "_policy_addon.html"
DASHBOARD_STEM = "_policy_dashboard"


def addon_filename(region: str) -> str:
    return f"{region}{ADDON_SUFFIX}"


def dashboard_filename(region: str, tracker: str | None = None) -> str:
    """Dashboard filename, tagged with the tracker it was built for.

    The output directory already names the lens, so the tag is redundant on
    disk. It is there because these files are published and downloaded one at a
    time, and away from their directory two files both called
    ``eap_policy_dashboard.html`` cannot be told apart.
    """
    return f"{region}{DASHBOARD_STEM}_{get_tracker(tracker)['file_suffix']}.html"


def tracker_dir(base_dir: Path, tracker: str | None = None) -> Path:
    """Per-tracker subdirectory of an addon or dashboard output tree."""
    return base_dir / get_tracker(tracker)["out_subdir"]


def workbook_dir(base_dir: Path, tracker: str | None = None) -> Path:
    subdir = get_tracker(tracker)["subdir"]
    return base_dir / subdir if subdir else base_dir


def tracker_label(tracker: str | None = None) -> str:
    return get_tracker(tracker)["label"]


def check_region(region: str, tracker: str | None = None) -> None:
    """Raise when a lens is not defined for a region.

    A lens declares ``regions`` only when its keywords do not exist everywhere.
    Falling back to English is silent by design -- it keeps a source's own
    translated ``core`` when a newer theme has none -- so a lens whose whole
    subject is that newer theme has to refuse the regions it cannot measure.
    """
    allowed = get_tracker(tracker).get("regions")
    if allowed and region not in allowed:
        raise ValueError(
            f"tracker '{tracker or DEFAULT_TRACKER}' is defined for "
            f"{', '.join(allowed)} only, because its keyword pack is not "
            f"translated elsewhere; got region '{region}'"
        )


KEYWORDS_EN = Path(__file__).resolve().parents[1] / "analysis" / "keywords" / "en"


def tracker_groups(family: str, tracker: str | None = None) -> list[str]:
    """Keyword group names a tracker displays for ``topics`` or ``actors``.

    Read from the English pack, which is the source of truth for which groups
    a theme defines. Only names are needed here, so this stays independent of
    the analysis package and its language-resolution rules.

    A theme may define one family and not the other -- El Nino is a named
    phenomenon with topics but no actors of its own -- so a missing file is a
    gap, not an error. A theme missing from *every* family is a typo, and
    still raises.
    """
    import json

    cfg = get_tracker(tracker)
    names: list[str] = []
    for theme in cfg["themes"]:
        path = KEYWORDS_EN / family / f"{theme}.json"
        if not path.exists():
            if not any(
                (fam / f"{theme}.json").exists()
                for fam in KEYWORDS_EN.iterdir()
                if fam.is_dir()
            ):
                raise ValueError(
                    f"tracker names theme '{theme}', which no family defines"
                )
            continue
        with open(path, encoding="utf-8") as fh:
            names.extend(json.load(fh))
    names.extend(cfg[f"extra_{family}"])
    return names


def group_terms(family: str = "topics") -> dict[str, list[str]]:
    """Every group's English term list, keyed by group name.

    This is what a group *is*. The dashboard has always shown the name and the
    number and never the definition, which is why two pills measuring the same
    concept with different vocabularies look like a contradiction rather than
    like two vocabularies -- and why nobody could tell whether a flat topic
    meant a quiet month or a term that never fires.

    The English pack is the controlled vocabulary: every other language's file
    translates these same concepts, so one map annotates a multi-language
    region correctly at the concept level. Read from disk here for the same
    reason ``tracker_groups`` does -- the plotting side does not import the
    analysis package.
    """
    import json

    out: dict[str, list[str]] = {}
    for path in sorted((KEYWORDS_EN / family).glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            for group, val in json.load(fh).items():
                # CJK packs store a group as {english gloss: term}; English is
                # a flat list. Only the terms are wanted either way.
                out[group] = list(val.values()) if isinstance(val, dict) else list(val)
    return out


def tracker_chip_groups(family: str, tracker: str | None = None) -> list[dict]:
    """Ordered pill sections for a tracker's chip list, or [] for a flat list.

    Declared per tracker rather than branched on a tracker name, so a new lens
    opts in by adding a key and every other lens keeps the flat list it had.
    """
    return get_tracker(tracker).get(f"{family}_chip_groups", [])
