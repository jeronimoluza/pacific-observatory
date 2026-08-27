"""Invariants for the themed keyword layout and per-tracker group selection.

The layout splits each keyword family into one file per theme:

    src/text/analysis/keywords/{language}/{family}/{theme}.json

Every build computes every theme; a tracker selects the slice it displays.
These tests pin the properties that make that safe — no group defined twice,
no tracker asking for a group nobody defines, and English present for every
theme so a missing translation always has somewhere to fall back to.
"""

import json
from pathlib import Path

import pytest

from src.text.analysis.utils import (
    KEYWORD_FAMILIES,
    available_themes,
    load_all_groups,
    resolved_language,
)
from src.text.plotting.trackers import TRACKERS, tracker_groups

KEYWORDS = Path("src/text/analysis/keywords")
LANGUAGES = sorted(p.name for p in KEYWORDS.iterdir() if p.is_dir())


@pytest.mark.parametrize("family", KEYWORD_FAMILIES)
def test_english_defines_every_theme(family):
    """English is the fallback for every theme, so it must define them all."""
    themes = available_themes(family)
    assert themes, f"no themes found for {family}"
    for theme in themes:
        assert (KEYWORDS / "en" / family / f"{theme}.json").exists()


@pytest.mark.parametrize("family", KEYWORD_FAMILIES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_no_group_is_defined_by_two_themes(language, family):
    """A group belongs to exactly one theme, or the merge is order-dependent."""
    seen: dict[str, str] = {}
    for theme in available_themes(family):
        path = KEYWORDS / language / family / f"{theme}.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            for group in json.load(fh):
                assert group not in seen, (
                    f"{language}/{family}: '{group}' in both "
                    f"{seen[group]}.json and {theme}.json"
                )
                seen[group] = theme


@pytest.mark.parametrize("family", KEYWORD_FAMILIES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_language_group_names_match_english(language, family):
    """Group names are the shared namespace across languages.

    Terms are translated; group names are not. A language that renames a group
    silently drops that group's counts for its sources.
    """
    assert set(load_all_groups(family, language=language)) == set(
        load_all_groups(family, language="en")
    )


@pytest.mark.parametrize("family", KEYWORD_FAMILIES)
@pytest.mark.parametrize("tracker", sorted(TRACKERS))
def test_tracker_groups_exist_and_are_unique(tracker, family):
    """A tracker may only display groups that some theme actually defines."""
    selected = tracker_groups(family, tracker)
    assert len(selected) == len(set(selected)), f"{tracker}/{family} has duplicates"
    defined = set(load_all_groups(family, language="en"))
    assert (
        set(selected) <= defined
    ), f"{tracker}/{family} selects undefined groups: {set(selected) - defined}"


def test_trackers_sharing_a_group_share_its_definition():
    """Two trackers naming the same group must be showing the same number.

    This is the point of the shared namespace: `inflation_prices` on the food
    dashboard is the same series as `inflation_prices` on the fuel dashboard.
    """
    for family in KEYWORD_FAMILIES:
        by_tracker = {t: set(tracker_groups(family, t)) for t in TRACKERS}
        terms = load_all_groups(family, language="en")
        for a, groups_a in by_tracker.items():
            for b, groups_b in by_tracker.items():
                if a >= b:
                    continue
                for group in groups_a & groups_b:
                    # One definition exists, so equality is structural; assert
                    # it is reachable and non-empty rather than trivially true.
                    assert terms[group], f"{group} shared by {a}/{b} but has no terms"


@pytest.mark.parametrize(
    "short,canonical", [("zh", "chinese_simplified"), ("ja", "japanese")]
)
def test_short_codes_resolve_to_canonical_directories(short, canonical):
    """Config files tag sources with ISO codes; those must not fall back to English."""
    assert load_all_groups("topics", language=short) == load_all_groups(
        "topics", language=canonical
    )
    assert resolved_language(short, "topics") == canonical
