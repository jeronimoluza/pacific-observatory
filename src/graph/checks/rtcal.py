"""Red checks on ``prices.rtcal`` (PX-51), over ``<build>/trusted_observations_rtcal.parquet``.

- #1 red: imputed rows whose missingness type the release policy marks ``do_not_release``
  (types read from ``<build>/rtcal/selected_release_thresholds.csv``);
- #2 red: rows without local currency, FX, source or input_hash
  (``unit_value_local``, ``fx_rate``, ``currency``, ``source``, ``input_hash`` null);
  amarillo instead for fills with source and input_hash but all three local columns null:
  USD-only on purpose (month without a rate, or FX suspect, so Stage B does not publish it).

``read`` streams only those columns and keeps one row of counts per country; PX-52
(``graph.checks.pages``) reuses it.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

NODE = "prices.rtcal"
RTCAL_OBS = "trusted_observations_rtcal.parquet"
REQUIRED = ["unit_value_local", "fx_rate", "currency", "source", "input_hash"]
LOCAL = ["unit_value_local", "fx_rate", "currency"]


def dnr_types(build: Path) -> set[str]:
    path = build / "rtcal" / "selected_release_thresholds.csv"
    with open(path, newline="") as fh:
        return {
            r["missingness_type"]
            for r in csv.DictReader(fh)
            if r["production_action"].startswith("do_not_release")
        }


def read(build: Path, countries: list[str] | None = None) -> list[dict]:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds

    dnr = pa.array(sorted(dnr_types(build)), pa.string())
    data = ds.dataset(build / RTCAL_OBS)
    cols = ["country", "imputed", "rtcal_missingness_type", *REQUIRED]
    flt = pc.field("country").isin(countries) if countries else None
    acc: dict[str, dict] = {}
    for b in data.to_batches(columns=cols, filter=flt, batch_size=1_000_000):
        imputed = pc.fill_null(b.column("imputed"), False)
        flags = {
            "n_imputed": imputed,
            "n_dnr": pc.and_(
                imputed,
                pc.fill_null(
                    pc.is_in(
                        pc.cast(b.column("rtcal_missingness_type"), pa.string()), dnr
                    ),
                    False,
                ),
            ),
            **{f"null_{c}": pc.is_null(b.column(c)) for c in REQUIRED},
        }
        flags["n_missing"] = flags[f"null_{REQUIRED[0]}"]
        for c in REQUIRED[1:]:
            flags["n_missing"] = pc.or_(flags["n_missing"], flags[f"null_{c}"])
        usd_only = pc.and_(
            imputed,
            pc.and_(
                pc.invert(flags["null_source"]), pc.invert(flags["null_input_hash"])
            ),
        )
        for c in LOCAL:
            usd_only = pc.and_(usd_only, flags[f"null_{c}"])
        flags["n_usd_only"] = usd_only
        flags["n_missing"] = pc.and_(flags["n_missing"], pc.invert(usd_only))
        t = pa.table(
            {
                "country": pc.cast(b.column("country"), pa.string()),
                **{k: pc.cast(v, pa.int64()) for k, v in flags.items()},
            }
        )
        g = t.group_by("country").aggregate(
            [(k, "sum") for k in flags] + [("country", "count")]
        )
        for r in g.to_pylist():
            a = acc.setdefault(r["country"], {k: 0 for k in [*flags, "n_rows"]})
            a["n_rows"] += r["country_count"]
            for k in flags:
                a[k] += r[f"{k}_sum"]
    return [
        {"country": c, "n_trusted": a["n_rows"] - a["n_imputed"], **a}
        for c, a in sorted(acc.items())
    ]


def check(rows: list[dict]) -> list[dict]:
    """Registry hook: no observer reads the rtcal rows, so this only points at the direct run."""
    if not any(r["node"] == NODE for r in rows):
        return []
    return [
        {
            "node": NODE,
            "partition": "*",
            "color": "amarillo",
            "msg": "#1/#2 requieren corrida directa: python -m graph.checks.rtcal --build <build_wNN>",
        }
    ]


def evaluate(rows: list[dict]) -> list[dict]:
    out = []
    dnr = sum(r["n_dnr"] for r in rows)
    missing = sum(r["n_missing"] for r in rows)
    fills = sum(r["n_imputed"] for r in rows)
    if dnr:
        top = ", ".join(
            f"{r['country']} {r['n_dnr']:,}"
            for r in sorted(rows, key=lambda r: -r["n_dnr"])[:5]
            if r["n_dnr"]
        )
        out.append(
            {
                "node": NODE,
                "partition": "*",
                "color": "rojo",
                "msg": f"#1 {dnr:,} de {fills:,} fills do_not_release mergeados ({top})",
            }
        )
    if missing:
        cols = ", ".join(f"{c} {sum(r[f'null_{c}'] for r in rows):,}" for c in REQUIRED)
        out.append(
            {
                "node": NODE,
                "partition": "*",
                "color": "rojo",
                "msg": f"#2 {missing:,} filas sin moneda local/fx/fuente/input_hash "
                f"({fills:,} imputadas; nulos: {cols})",
            }
        )
    usd = sum(r["n_usd_only"] for r in rows)
    if usd:
        top = ", ".join(
            f"{r['country']} {r['n_usd_only']:,}"
            for r in sorted(rows, key=lambda r: -r["n_usd_only"])[:5]
            if r["n_usd_only"]
        )
        out.append(
            {
                "node": NODE,
                "partition": "*",
                "color": "amarillo",
                "msg": f"#2 {usd:,} fills solo en USD (sin tasa o FX sospechoso; {top})",
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m graph.checks.rtcal")
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
        f"{a.build / RTCAL_OBS}: {sum(r['n_rows'] for r in rows):,} filas, "
        f"{sum(r['n_imputed'] for r in rows):,} imputadas, {len(rows)} países"
    )
    findings = evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<6} {f['msg']}")
    if not findings:
        print("verde")
    return 1 if any(f["color"] == "rojo" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
