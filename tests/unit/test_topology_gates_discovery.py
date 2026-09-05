"""regions.yaml decides what a country is, not the filesystem.

Both the build and publish discovered units by walking directories. A folder
left behind by a rename therefore became a country in its own right:
``data/text/eap/southeast_asia/lao`` sat alongside ``lao_pdr`` holding copies of
the same five sources. It reached the dashboard labelled with its raw slug --
``countries.yaml`` has an entry for ``lao_pdr`` but none for ``lao``, so
``get_label`` fell through to the slug -- and because source keys are built as
``<country>_<newspaper>``, ``lao_kpl`` and ``lao_pdr_kpl`` never deduped and
roughly 30k articles were counted twice in the subregion and region aggregates.
"""

from src.core.config import known_country_slugs


def test_canonical_lao_slug_is_known():
    assert "lao_pdr" in known_country_slugs()


def test_stale_rename_slug_is_not_known():
    """The regression: `lao` must not qualify as a country."""
    assert "lao" not in known_country_slugs()


def test_topology_is_populated():
    """A silently empty set would disable the gate rather than enforce it."""
    slugs = known_country_slugs()
    assert len(slugs) > 100
    for expected in ("fiji", "vietnam", "mongolia", "nauru", "taiwan_china"):
        assert expected in slugs


def _admitted(region, sub, country):
    """The gate the build and publish both apply."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src" / "text" / "configs"
    if country in known_country_slugs():
        return True
    return (root / region / sub / country).is_dir()


def test_stale_data_dir_without_configs_is_rejected():
    """`lao` has no config directory -- only `lao_pdr` does."""
    assert not _admitted("eap", "southeast_asia", "lao")
    assert _admitted("eap", "southeast_asia", "lao_pdr")


def test_configured_non_country_is_admitted():
    """`pacific` is a region-wide RNZ feed, absent from regions.yaml but real.

    A topology-only gate would have discarded its ~10.7k articles, so carrying
    scraper configs has to be sufficient on its own.
    """
    assert "pacific" not in known_country_slugs()
    assert _admitted("eap", "pacific_islands", "pacific")


def test_every_text_config_dir_survives_the_gate():
    """No configured source may be unreachable because of this filter."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src" / "text" / "configs"
    offenders = set()
    for region in root.iterdir():
        if not region.is_dir() or region.name.startswith(("_", ".")):
            continue
        for sub in region.iterdir():
            if not sub.is_dir() or sub.name.startswith(("_", ".")):
                continue
            for country in sub.iterdir():
                if not country.is_dir() or country.name.startswith(("_", ".")):
                    continue
                if not _admitted(region.name, sub.name, country.name):
                    offenders.add(f"{region.name}/{sub.name}/{country.name}")
    assert not offenders, f"configured dirs rejected by the gate: {sorted(offenders)}"
