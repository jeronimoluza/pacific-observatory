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


def run_publish(region=None, subregion=None, country=None):
    """Build dashboard_data.json and generate EPU dashboards."""
    units = _discover_units(region=region, subregion=subregion, country=country)

    click.echo()
    click.echo("  Text publish (dashboards)")
    click.echo("  " + "-" * 40)

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


def run_publish_special(region: str):
    """Build the per-region Fuel Crisis Policy + EPU dashboard for ``region``.

    Builds (or refreshes) a region-scoped
    ``outputs/text/dashboard_data/dashboard_data_{region}.json``
    from current outputs and renders the dashboard HTML.
    """
    from text.plotting.small_dashboard_integrated_w_policy import (
        available_regions,
        generate_dashboard_from_json,
    )

    click.echo()
    click.echo("  Text publish-special (regional Fuel Crisis Policy dashboard)")
    click.echo("  " + "-" * 40)

    regions = available_regions()
    if region not in regions:
        raise click.ClickException(
            f"No Fuel Crisis Policy addon for region '{region}'. "
            f"Available: {', '.join(regions) or '(none)'}"
        )

    region_json = DASHBOARD_DATA_DIR / f"dashboard_data_{region}.json"

    click.echo(f"  Region: {region}")
    click.echo(f"  Building {region_json.name} from outputs/text/...")
    units = _discover_units(region=region)
    if not units:
        raise click.ClickException(
            f"No units with EPU data found for region '{region}'. "
            f"Run 'po text build --region {region}' first."
        )
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(region_json, "w", encoding="utf-8") as f:
        json.dump(_build_dashboard_json(units), f, indent=2, default=str)
    click.echo(f"  Written: {region_json.relative_to(PROJECT_ROOT)}")

    try:
        out_path = generate_dashboard_from_json(region_json, region)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))
    click.echo(f"  Written: {out_path.relative_to(PROJECT_ROOT)}")
