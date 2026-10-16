"""Page check (PX-52): a country with 0 trusted rows is not published (#3, #12, #18).

Over a build dir:
- red: a country in ``trusted_observations_rtcal.parquet`` (what the pages read) whose
  rows are all imputed (#3);
- yellow: a country with non-food observations but 0 trusted non-food rows (#12);
  skipped when the build has no non-food files;
- yellow: a country with price manifests under ``src/prices/configs`` and no row at all
  in the rtcal file (#18, "sin datos").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from graph.checks import rtcal

NODE = "prices.pages"
NONFOOD = (
    "global_prices_nonfood_observations.parquet",
    "global_prices_nonfood_trusted_observations.parquet",
)


def _country_counts(path: Path, countries: list[str] | None) -> dict[str, int]:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds

    flt = pc.field("country").isin(countries) if countries else None
    out: dict[str, int] = {}
    for b in ds.dataset(path).to_batches(
        columns=["country"], filter=flt, batch_size=2_000_000
    ):
        vc = pc.value_counts(pc.cast(b.column("country"), pa.string()))
        for v in vc.to_pylist():
            out[v["values"]] = out.get(v["values"], 0) + v["counts"]
    return out


def manifest_countries() -> set[str]:
    from prices.config import discover_prices_configs

    return {p.parent.name for p in discover_prices_configs()}


def read(build: Path, countries: list[str] | None = None) -> list[dict]:
    by_country = {r["country"]: r for r in rtcal.read(build, countries)}
    nf = None
    if all((build / f).exists() for f in NONFOOD):
        nf = [_country_counts(build / f, countries) for f in NONFOOD]
    expected = manifest_countries()
    if countries:
        expected &= set(countries)
    rows = []
    for c in sorted(expected | set(by_country)):
        r = by_country.get(c, {})
        rows.append(
            {
                "country": c,
                "n_rows": r.get("n_rows", 0),
                "n_trusted": r.get("n_trusted", 0),
                "n_imputed": r.get("n_imputed", 0),
                "has_manifest": c in expected,
                "nf_rows": nf[0].get(c, 0) if nf else None,
                "nf_trusted": nf[1].get(c, 0) if nf else None,
            }
        )
    return rows


def check(rows: list[dict]) -> list[dict]:
    """Registry hook: the pages observer only sees page files, so this points at the direct run."""
    if not any(r["node"] == NODE for r in rows):
        return []
    return [
        {
            "node": NODE,
            "partition": "*",
            "color": "amarillo",
            "msg": "#3/#12/#18 requieren corrida directa: python -m graph.checks.pages --build <build_wNN>",
        }
    ]


def evaluate(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        c = r["country"]
        if r["n_rows"] and not r["n_trusted"]:
            out.append(
                {
                    "node": NODE,
                    "partition": c,
                    "color": "rojo",
                    "msg": f"#3 publicado con 0 filas confiables ({r['n_imputed']:,} imputadas)",
                }
            )
        elif not r["n_rows"] and r["has_manifest"]:
            out.append(
                {
                    "node": NODE,
                    "partition": c,
                    "color": "amarillo",
                    "msg": "#18 sin datos: tiene manifiestos y 0 filas en la página",
                }
            )
        if r["nf_rows"] and not r["nf_trusted"]:
            out.append(
                {
                    "node": NODE,
                    "partition": c,
                    "color": "amarillo",
                    "msg": f"#12 non-food: {r['nf_rows']:,} filas, 0 confiables",
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m graph.checks.pages")
    ap.add_argument(
        "--build", type=Path, required=True, help="build dir, e.g. .../build_w42"
    )
    ap.add_argument(
        "--countries", help="comma-separated slugs or a panel name (panel36)"
    )
    a = ap.parse_args(argv)
    countries = None
    if a.countries:
        from prices.weekly.panels import resolve_countries

        countries = resolve_countries(a.countries)
    rows = read(a.build, countries)
    print(
        f"{a.build}: {len(rows)} países, {sum(1 for r in rows if r['n_trusted'])} con filas confiables"
        + ("" if rows and rows[0]["nf_rows"] is not None else "; sin archivos non-food")
    )
    findings = evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<24} {f['msg']}")
    if not findings:
        print("verde")
    return 1 if any(f["color"] == "rojo" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
