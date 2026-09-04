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


TRACKERS = {
    "fuel": {
        "slug": "fuel",
        "label": "Fuel Crisis Policy",
        "out_subdir": "fuel",
        "aria_subject": "fuel-crisis",
        "subdir": "",
        "themes": ["core"],
        "extra_topics": [],
        "extra_actors": [],
    },
    "food": {
        "slug": "food_security",
        "label": "Food Security Policy",
        "out_subdir": "food_security",
        "aria_subject": "food-security",
        "subdir": "food_security",
        "themes": ["food"],
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
        # The Topics tab deliberately shows the whole 43-group universe, not
        # the tracker's own eighteen -- a food index of 150 means nothing until
        # you can see governance sitting at 300. Forty-three pills in one row
        # is a wall, so they are sectioned. Food and climate open by default;
        # they carry the topics this lens exists to show. The rest stay one
        # click away rather than one scroll away.
        "topics_chip_groups": [
            {
                "label": "Food & Agriculture",
                "expanded": True,
                "topics": [
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
            },
            {
                "label": "Climate & Environment",
                "expanded": True,
                "topics": [
                    "drought_water",
                    "extreme_weather_disaster",
                    "climate_environment",
                ],
            },
            {
                "label": "Hunger, Poverty & Social",
                "topics": [
                    "hunger_malnutrition",
                    "food_assistance",
                    "poverty",
                    "inequality",
                    "health",
                    "education",
                    "gender_equality",
                ],
            },
            {
                "label": "Macro & Prices",
                "topics": [
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
            },
            {
                "label": "Energy & Fuel",
                "topics": [
                    "energy",
                    "oil",
                    "gasoline",
                    "diesel",
                    "natural_gas",
                    "fuel_rationing",
                ],
            },
            {
                "label": "Governance & Shocks",
                "topics": [
                    "political_stability",
                    "corruption_governance",
                    "armed_conflicts",
                    "covid_pandemic",
                    "us_china_trade_war",
                    "labor_market",
                    "housing_real_estate",
                    "infrastructure",
                ],
            },
        ],
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
DASHBOARD_SUFFIX = "_policy_dashboard.html"


def addon_filename(region: str) -> str:
    return f"{region}{ADDON_SUFFIX}"


def dashboard_filename(region: str) -> str:
    return f"{region}{DASHBOARD_SUFFIX}"


def tracker_dir(base_dir: Path, tracker: str | None = None) -> Path:
    """Per-tracker subdirectory of an addon or dashboard output tree.

    The directory carries the lens, so filenames stay uniform across
    trackers and a new lens needs no naming decision.
    """
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
    """
    import json

    cfg = get_tracker(tracker)
    names: list[str] = []
    for theme in cfg["themes"]:
        path = KEYWORDS_EN / family / f"{theme}.json"
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
