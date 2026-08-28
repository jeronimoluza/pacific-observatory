"""Text publish stage: build dashboard_data.json and generate EPU dashboards."""

import json
from pathlib import Path

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "text"
DASHBOARD_DATA_DIR = OUTPUT_DIR / "dashboard_data"
DASHBOARD_JSON = DASHBOARD_DATA_DIR / "dashboard_data.json"


def _discover_units(region=None, subregion=None, country=None):
    """Walk outputs/text/{region}/{subregion}/{country|_aggregate}/ for epu.csv.

    Returns list of dicts with keys: slug, label, level, region, subregion,
    output_dir.
    """
    if not OUTPUT_DIR.exists():
        return []

    try:
        from core.config import get_label
    except ImportError:
        get_label = None

    units = []

    for region_dir in sorted(OUTPUT_DIR.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith((".", "_")):
            continue
        rgn = region_dir.name

        # Region _aggregate
        rgn_agg = region_dir / "_aggregate"
        if rgn_agg.is_dir() and (rgn_agg / "epu" / "epu.csv").exists():
            if (not region or region == rgn) and not subregion and not country:
                label = get_label(rgn) if get_label else rgn
                units.append(
                    {
                        "slug": rgn,
                        "label": label,
                        "level": "region",
                        "region": rgn,
                        "subregion": None,
                        "output_dir": rgn_agg,
                    }
                )

        for sub_dir in sorted(region_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith((".", "_")):
                continue
            sub = sub_dir.name

            # Subregion _aggregate
            sub_agg = sub_dir / "_aggregate"
            if sub_agg.is_dir() and (sub_agg / "epu" / "epu.csv").exists():
                if (
                    (not region or region == rgn)
                    and (not subregion or subregion == sub)
                    and not country
                ):
                    label = get_label(sub) if get_label else sub
                    units.append(
                        {
                            "slug": sub,
                            "label": label,
                            "level": "subregion",
                            "region": rgn,
                            "subregion": sub,
                            "output_dir": sub_agg,
                        }
                    )

            for country_dir in sorted(sub_dir.iterdir()):
                if not country_dir.is_dir() or country_dir.name.startswith((".", "_")):
                    continue
                ctry = country_dir.name
                if not (country_dir / "epu" / "epu.csv").exists():
                    continue

                if region and region != rgn:
                    continue
                if subregion and subregion != sub:
                    continue
                if country and country.lower() != ctry.lower():
                    continue

                label = get_label(ctry) if get_label else ctry
                units.append(
                    {
                        "slug": ctry,
                        "label": label,
                        "level": "country",
                        "region": rgn,
                        "subregion": sub,
                        "output_dir": country_dir,
                    }
                )

    return units


def _read_epu_csv(output_dir: Path) -> list | None:
    path = output_dir / "epu" / "epu.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")


def _read_topics_csv(output_dir: Path) -> list | None:
    path = output_dir / "epu" / "topics_epu.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")


def _read_actors_csv(output_dir: Path) -> list | None:
    path = output_dir / "epu" / "actors_epu.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="utf-8")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")


def _read_attribution(output_dir: Path) -> dict:
    attr_dir = output_dir / "uncertainty_attribution"
    if not attr_dir.exists():
        return {}
    result = {}
    for csv_path in sorted(attr_dir.glob("*.csv")):
        df = pd.read_csv(csv_path, encoding="utf-8")
        result[csv_path.stem] = df.to_dict(orient="records")
    return result


def _build_tree(units: list) -> list:
    """Build a hierarchical tree structure sorted alphabetically by label.

    Returns list of nodes: [{slug, label, level, children?}, ...].
    Regions → subregions → countries, each level sorted by label.
    """
    from collections import defaultdict

    try:
        from core.config import get_label as _get_label
    except ImportError:
        _get_label = None

    def _label(slug: str) -> str:
        return _get_label(slug) if _get_label else slug

    regions = {}
    subregions = defaultdict(dict)
    countries = defaultdict(list)

    for u in units:
        rgn = u["region"]
        sub = u["subregion"]
        level = u["level"]

        if level == "region":
            regions[rgn] = {"slug": u["slug"], "label": u["label"], "level": "region"}
        elif level == "subregion":
            subregions[rgn][sub] = {
                "slug": u["slug"],
                "label": u["label"],
                "level": "subregion",
            }
        elif level == "country":
            countries[(rgn, sub)].append(
                {"slug": u["slug"], "label": u["label"], "level": "country"}
            )

    # Collect all region slugs
    all_regions = set(u["region"] for u in units)
    tree = []
    for rgn in sorted(all_regions, key=lambda r: r):
        region_label = regions.get(rgn, {}).get("label", _label(rgn))
        region_node = {
            "slug": rgn,
            "label": region_label,
            "level": "region",
            "children": [],
        }
        # Subregions in this region
        all_subs = {
            u["subregion"] for u in units if u["region"] == rgn and u["subregion"]
        }
        for sub in sorted(
            all_subs, key=lambda s: subregions[rgn].get(s, {}).get("label", _label(s))
        ):
            sub_label = subregions[rgn].get(sub, {}).get("label", _label(sub))
            sub_node = {
                "slug": sub,
                "label": sub_label,
                "level": "subregion",
                "children": [],
            }
            for ctry_node in sorted(
                countries.get((rgn, sub), []), key=lambda c: c["label"]
            ):
                sub_node["children"].append(ctry_node)
            region_node["children"].append(sub_node)

        tree.append(region_node)

    return sorted(tree, key=lambda n: n["label"])


def _build_dashboard_json(units: list) -> dict:
    """Build the full dashboard_data.json payload."""
    data = {
        "metadata": {
            "generated_at": pd.Timestamp.now().isoformat(),
            "units": len(units),
        },
        "tree": _build_tree(units),
        "units": {},
    }

    for u in units:
        slug = u["slug"]
        level = u["level"]
        # Use composite key for aggregates to avoid collisions
        key = slug if level == "country" else f"{level}:{slug}"
        output_dir = u["output_dir"]

        data["units"][key] = {
            "slug": slug,
            "label": u["label"],
            "level": level,
            "region": u["region"],
            "subregion": u["subregion"],
            "epu": _read_epu_csv(output_dir),
            "topics": _read_topics_csv(output_dir),
            "actors": _read_actors_csv(output_dir),
            "attribution": _read_attribution(output_dir),
        }

    return data


_ID_COLS = ["date", "ym", "region", "subregion", "unit_slug", "level", "label"]


def _stack_family(
    units: list, family_filename: str, subdir: str = "epu"
) -> pd.DataFrame:
    """Read one family CSV (default epu/) across units, stacked."""
    rows = []
    for u in units:
        path = u["output_dir"] / subdir / family_filename
        if not path.exists():
            continue
        df = pd.read_csv(path, encoding="utf-8")
        df["region"] = u["region"]
        df["subregion"] = u["subregion"]
        df["unit_slug"] = u["slug"]
        df["level"] = u["level"]
        df["label"] = u["label"]
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False)


def _front_id_cols(df: pd.DataFrame) -> pd.DataFrame:
    front = [c for c in _ID_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in front]
    return df[front + rest]


def _export_region_panel(
    region: str, units: list, database_status: dict | None = None
) -> Path:
    """Write outputs/text/dashboard_data/{json,csv,xlsx,dta}/<region>.<ext>.

    JSON: hierarchical dashboard payload (same shape as the global JSON,
    scoped to this region). CSV/DTA: long-on-unit, wide-on-index panel
    merging EPU + topics + actors. XLSX: one sheet per family plus a
    combined ``panel`` sheet, standalone ``topics_framing``/
    ``actors_framing`` sheets for the uncertainty-attribution data, and a
    ``sources`` sheet (per-source provenance) when ``database_status`` is
    available for this region.
    """
    json_dir = DASHBOARD_DATA_DIR / "json"
    csv_dir = DASHBOARD_DATA_DIR / "csv"
    xlsx_dir = DASHBOARD_DATA_DIR / "xlsx"
    dta_dir = DASHBOARD_DATA_DIR / "dta"
    for d in (json_dir, csv_dir, xlsx_dir, dta_dir):
        d.mkdir(parents=True, exist_ok=True)

    region_json = json_dir / f"{region}.json"
    with open(region_json, "w", encoding="utf-8") as f:
        json.dump(_build_dashboard_json(units), f, indent=2, default=str)

    epu_df = _stack_family(units, "epu.csv")
    topics_df = _stack_family(units, "topics_epu.csv")
    actors_df = _stack_family(units, "actors_epu.csv")
    topics_framing_df = _stack_family(units, "topics.csv", "uncertainty_attribution")
    actors_framing_df = _stack_family(units, "actors.csv", "uncertainty_attribution")

    if (
        epu_df.empty
        and topics_df.empty
        and actors_df.empty
        and topics_framing_df.empty
        and actors_framing_df.empty
    ):
        return region_json

    merged: pd.DataFrame | None = None
    for df in (epu_df, topics_df, actors_df):
        if df.empty:
            continue
        if merged is None:
            merged = df.copy()
            continue
        merge_keys = [c for c in _ID_COLS if c in merged.columns and c in df.columns]
        new_cols = merge_keys + [c for c in df.columns if c not in merged.columns]
        merged = merged.merge(df[new_cols], on=merge_keys, how="outer")

    if merged is not None:
        merged = (
            _front_id_cols(merged)
            .sort_values(["unit_slug", "date"], kind="stable")
            .reset_index(drop=True)
        )

        csv_path = csv_dir / f"{region}.csv"
        merged.to_csv(csv_path, index=False, encoding="utf-8")

        dta_path = dta_dir / f"{region}.dta"
        dta_df = merged.copy()
        dta_df["date"] = pd.to_datetime(dta_df["date"], errors="coerce")
        for c in dta_df.select_dtypes(include="object").columns:
            dta_df[c] = dta_df[c].fillna("").astype(str)
        dta_df.to_stata(dta_path, write_index=False, version=118)

    xlsx_path = xlsx_dir / f"{region}.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        for sheet, df in (
            ("epu", epu_df),
            ("topics", topics_df),
            ("actors", actors_df),
            ("topics_framing", topics_framing_df),
            ("actors_framing", actors_framing_df),
        ):
            if df.empty:
                continue
            _front_id_cols(df).to_excel(xw, sheet_name=sheet, index=False)
        if merged is not None:
            _front_id_cols(merged).to_excel(xw, sheet_name="panel", index=False)
        _write_sources_sheet(xw, database_status, region)

    return region_json


def _write_sources_sheet(xw, database_status: dict | None, region: str) -> None:
    """Append a ``sources`` sheet scoped to ``region``, if status data allows.

    Never raises: a status failure or empty region slice just skips the sheet.
    """
    if not database_status:
        return
    try:
        from text.status import DATABASE_STATUS_FIELDS

        rows = [
            r for r in database_status.get("sources", []) if r.get("region") == region
        ]
        if rows:
            pd.DataFrame(rows, columns=DATABASE_STATUS_FIELDS).to_excel(
                xw, sheet_name="sources", index=False
            )
    except Exception:  # noqa: BLE001
        pass


def _render_fcp_dashboard(
    region: str, region_json: Path, tracker: str | None = None
) -> Path | None:
    """Render the regional policy + EPU HTML if an addon exists."""
    from text.plotting.small_dashboard_integrated_w_policy import (
        available_regions,
        generate_dashboard_from_json,
    )

    if region not in available_regions(tracker):
        return None
    return generate_dashboard_from_json(region_json, region, tracker)


def _refresh_database_status():
    """Regenerate the global outputs/text/database_status/sources.{csv,json,xlsx} snapshot.

    Scope-independent: always reflects the whole data/text/ database. Failures
    here never block dashboard publishing. Returns the computed data dict (also
    used to populate the per-region ``sources`` xlsx sheet), or None on failure.
    """
    from text.status import compute_database_status, write_database_status

    try:
        data = compute_database_status()
        write_database_status(data)
        t = data["totals"]
        click.echo(
            f"  Database status: {t['sources']} sources · "
            f"{t['articles_total']:,} articles → outputs/text/database_status/"
        )
        return data
    except Exception as e:  # noqa: BLE001
        click.echo(f"  Database status refresh failed: {e}")
        return None


def run_publish(
    region=None,
    subregion=None,
    country=None,
    tracker=None,
    skip_database_status=False,
):
    """Build dashboard_data.json, per-region panels, and EPU dashboards.

    ``skip_database_status`` bypasses the global raw-data rescan, which is
    pointless when the published regions have no local ``data/text/`` copy.

    Always writes the global ``outputs/text/dashboard_data/dashboard_data.json``
    and renders the basic integrated HTML. When the scope covers full
    regions (no ``--subregion``/``--country`` filter), also writes per-region
    ``outputs/text/dashboard_data/{json,csv,xlsx,dta}/<region>.<ext>`` and
    renders the regional Fuel Crisis Policy HTML where an addon exists.
    """
    units = _discover_units(region=region, subregion=subregion, country=country)

    click.echo()
    click.echo("  Text publish (dashboards)")
    click.echo("  " + "-" * 40)

    if skip_database_status:
        click.echo("  Database status: skipped (--skip-database-status)")
        database_status = None
    else:
        database_status = _refresh_database_status()

    if not units:
        click.echo("  No units with EPU data found. Run 'po text build' first.")
        return

    country_units = [u for u in units if u["level"] == "country"]
    agg_units = [u for u in units if u["level"] != "country"]
    click.echo(
        f"  Countries: {', '.join(u['slug'] for u in country_units) or '(none)'}"
    )
    if agg_units:
        click.echo(
            f"  Aggregates: {', '.join(u['slug'] + ' (' + u['level'] + ')' for u in agg_units)}"
        )
    click.echo()

    click.echo("  Building dashboard_data.json...")
    dashboard = _build_dashboard_json(units)

    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_JSON, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, default=str)

    click.echo(f"  Written: {DASHBOARD_JSON.relative_to(PROJECT_ROOT)}")

    try:
        from text.plotting.small_dashboard_integrated import (
            generate_dashboard_from_json,
        )

        generate_dashboard_from_json(DASHBOARD_JSON)
    except (ImportError, AttributeError):
        click.echo(
            "  Dashboard generator not yet updated for JSON input. Skipping HTML."
        )
    except Exception as e:
        click.echo(f"  Dashboard generation failed: {e}")

    if subregion or country:
        click.echo(
            "  Skipping per-region panels and Fuel Crisis Policy dashboards "
            "(scope is narrower than a full region)."
        )
        return

    regions_in_scope = sorted({u["region"] for u in units})
    for rgn in regions_in_scope:
        rgn_units = [u for u in units if u["region"] == rgn]
        click.echo(f"  Building {rgn}/ panel from outputs/text/...")
        region_json = _export_region_panel(rgn, rgn_units, database_status)
        click.echo(
            f"  Written: {DASHBOARD_DATA_DIR.relative_to(PROJECT_ROOT)}/"
            f"{{json,csv,xlsx,dta}}/{rgn}.<ext>"
        )

        try:
            fcp_html = _render_fcp_dashboard(rgn, region_json, tracker)
        except (FileNotFoundError, ValueError) as exc:
            click.echo(f"  Policy dashboard for {rgn}: {exc}")
            continue
        if fcp_html is not None:
            click.echo(f"  Written: {fcp_html.relative_to(PROJECT_ROOT)}")
