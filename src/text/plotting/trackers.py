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
