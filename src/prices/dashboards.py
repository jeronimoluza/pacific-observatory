"""Both price dashboards -- the explorer and the published dashboard -- from one
build directory, in two variants:

  rtcal    RT-CAL fills drawn and pruned cells removed (the build's `rtcal/`)
  trusted  trusted observations only: no fills, nothing pruned

Each variant is rendered for the world and for EAP, so one call writes eight
pages under OUT_DIR/<variant>/.

Every path the two renderers read or write is a module constant bound at import
(`explorer.sources`, `explorer.aggregate`, `publish`, `rtcal.config`,
`build.leaf_typical_mass`), and in a worktree whose `data/` is a weekly tree,
`data/prices/build` can still be a production build. Each is re-pointed here
before anything renders: every Path constant under the default build directory
is moved under BUILD_DIR, the same relative path. The suppressed-unit
audits both renderers write go to OUT_DIR/<variant>/, never the build.

Without `leaf_typical_mass.csv` in the build directory, piece rows that need a
typical mass to convert are suppressed; both renderers log it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import click
import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

VARIANTS = ("rtcal", "trusted")
REGIONS = (None, "eap")
OBS_FILE = "global_prices_observations.parquet"

# What `publish` reads off the observations, found by searching publish.py,
# unit_collapse.py and sold_by_item.py for every column name the build writes.
# `publish` keeps only qa_status == "trusted" rows, so the filter is pushed into
# the read; all 32 columns of every row do not fit on a 26 GB box.
_PUBLISH_COLS = [
    "product_name", "observation_date", "month", "coicop_code", "pricing_basis",
    "amount_value", "standard_unit", "unit_value_local", "unit_value_usd",
    "trusted", "country", "qa_status", "mass_source", "trust_level",
]


def _modules():
    from prices import publish
    from prices.build import leaf_typical_mass
    from prices.explorer import aggregate, sources
    from prices.rtcal import config

    return publish, leaf_typical_mass, aggregate, sources, config


def _rebase(old: Path, new: Path) -> None:
    """Every Path constant under `old` in the renderers' modules, moved to `new`."""
    for mod in _modules():
        for name, value in list(vars(mod).items()):
            if isinstance(value, Path) and value.is_relative_to(old):
                setattr(mod, name, new / value.relative_to(old))


def _point_at(build_dir: Path, out_dir: Path, variant: str, region: str | None) -> None:
    publish, _, _, sources, config = _modules()
    from prices.rtcal import fills

    tag = f"_{region}" if region else ""
    sources.SUPPRESSED_PARQUET = out_dir / f"explorer_suppressed_units{tag}.parquet"
    publish.SUPPRESSED_PARQUET = out_dir / f"global_prices_suppressed_units{tag}.parquet"
    publish.read_observations = _trusted_observations
    publish.fills_mod = SimpleNamespace(
        CELL_KEY=fills.CELL_KEY,
        load_pruned_cells=fills.load_pruned_cells,
        load_released_fills=_released_fills,
    )
    # `trusted` points the loaders at files that do not exist, which is the
    # loaders' own "RT-CAL has not run" path: empty fills, nothing pruned.
    rtcal = build_dir / "rtcal" if variant == "rtcal" else out_dir / "_no_rtcal"
    config.RELEASED_FILLS_PARQUET = rtcal / "rtcal_v1_released_fills.parquet"
    config.PRUNED_CELLS_PARQUET = rtcal / "rtcal_v1_pruned_cells.parquet"


def _trusted_observations(path: Path) -> pd.DataFrame:
    from prices.explorer.stream import EXCLUDED_COUNTRIES

    keep = [("qa_status", "==", "trusted"), ("country", "not in", sorted(EXCLUDED_COUNTRIES))]
    return pq.read_table(path, columns=_PUBLISH_COLS, filters=keep).to_pandas()


def _released_fills() -> pd.DataFrame:
    from prices.explorer.stream import EXCLUDED_COUNTRIES
    from prices.rtcal import fills

    f = fills.load_released_fills()
    return f[~f.country.isin(EXCLUDED_COUNTRIES)]


@click.command("dashboards")
@click.option(
    "--build-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Build directory holding global_prices_observations.parquet and rtcal/.",
)
@click.option(
    "--out-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Where the pages go, one folder per variant. Default: BUILD_DIR/dashboards.",
)
@click.option(
    "--variant",
    "variants",
    multiple=True,
    type=click.Choice(VARIANTS),
    help="Render only this variant. Repeatable. Default: both.",
)
def dashboards(build_dir: Path, out_dir: Path | None, variants: tuple[str, ...]) -> None:
    """Explorer + dashboard, world + EAP, with and without RT-CAL, from one build."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from prices import explorer, publish

    _rebase(publish.BUILD_DIR, build_dir)
    out_dir = out_dir or build_dir / "dashboards"
    for variant in variants or VARIANTS:
        vdir = out_dir / variant
        vdir.mkdir(parents=True, exist_ok=True)
        for region in REGIONS:
            _point_at(build_dir, vdir, variant, region)
            tag = f"_{region}" if region else ""
            explorer.run(vdir / f"global_prices_explorer{tag}.html", region)
            publish.publish(region=region, out_path=vdir / f"global_prices_dashboard{tag}.html")
            click.echo(f"{variant} {region or 'world'}: {vdir}")
