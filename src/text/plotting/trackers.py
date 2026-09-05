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
tracker did before the pill list grew to the full forty-three groups.

Adding a tracker is one entry here plus a ``{theme}.json`` per family.
"""

from __future__ import annotations

from pathlib import Path

# The Topics tab deliberately shows the whole 43-group universe, not the
# tracker's own eighteen -- a food index of 150 means nothing until you can see
# governance sitting at 300. Forty-three pills in one row is a wall, so they are
# sectioned. The sections are the same for every tracker, because the universe
# is; only which ones open by default differs, and each tracker opens the ones
# its lens exists to show. The rest stay one click away rather than one scroll
# away.
_TOPIC_SECTIONS = [
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
    # The development-issues taxonomy: twenty-three broad buckets covering the
    # whole development agenda, deliberately coarser than the groups above and
    # overlapping them. Sectioned by the World Bank verticals the taxonomy
    # itself uses, so the split is the author's rather than ours. Every one of
    # these sections is collapsed on every tracker: they are context for a lens,
    # never the lens itself.
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


def _topic_chip_groups(expanded: set[str]) -> list[dict]:
    """The 43 topic pills as collapsible sections, opening ``expanded``."""
    return [
        {"label": label, "expanded": label in expanded, "topics": list(topics)}
        for label, topics in _TOPIC_SECTIONS
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


def tracker_chip_groups(family: str, tracker: str | None = None) -> list[dict]:
    """Ordered pill sections for a tracker's chip list, or [] for a flat list.

    Declared per tracker rather than branched on a tracker name, so a new lens
    opts in by adding a key and every other lens keeps the flat list it had.
    """
    return get_tracker(tracker).get(f"{family}_chip_groups", [])
