"""Policy-tracker variants sharing the workbook -> addon -> dashboard pipeline.

Each tracker is one crisis lens over the same six regional workbooks and the
same closed v6 (Category, Subcategory) taxonomy. ``fuel`` is the original and
stays the default so existing commands and filenames are unchanged.
"""

from __future__ import annotations

from pathlib import Path


TRACKERS = {
    "fuel": {
        "slug": "fuel",
        "label": "Fuel Crisis Policy",
        "addon_stem": "fuel_crisis_policy_dashboard",
        "aria_subject": "fuel-crisis",
        "subdir": "",
    },
    "food": {
        "slug": "food_security",
        "label": "Food Security Policy",
        "addon_stem": "food_security_policy_addon",
        "aria_subject": "food-security",
        "subdir": "food_security",
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


def addon_filename(region: str, tracker: str | None = None) -> str:
    return f"{region}_{get_tracker(tracker)['addon_stem']}.html"


def addon_suffix(tracker: str | None = None) -> str:
    return f"_{get_tracker(tracker)['addon_stem']}.html"


def workbook_dir(base_dir: Path, tracker: str | None = None) -> Path:
    subdir = get_tracker(tracker)["subdir"]
    return base_dir / subdir if subdir else base_dir


def tracker_label(tracker: str | None = None) -> str:
    return get_tracker(tracker)["label"]
