"""Audit fuel price per-source observations.csv files for schema, nulls, duplicates, and ranges.

Run directly::

    python -m src.cpi.fuel_prices.audit_csv

Outputs:
    data/cpi/fuel_prices/audit_report.md
    data/cpi/fuel_prices/audit_report.html (optional)
"""

from __future__ import annotations

import argparse
import html as _html
from datetime import date
from pathlib import Path
from typing import Any


def _read_csv(path: Path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for audit_csv") from exc

    df = pd.read_csv(path, low_memory=False)

    date_cols = ["observation_date", "effective_from", "effective_to", "scrape_ts"]
    date_info: dict[str, dict[str, int]] = {}
    for col in date_cols:
        if col in df.columns:
            raw = df[col]
            parsed = pd.to_datetime(raw, errors="coerce")
            invalid = parsed.isna() & raw.notna() & raw.astype(str).str.strip().ne("")
            date_info[col] = {
                "invalid": int(invalid.sum()),
                "missing": int(raw.isna().sum()),
            }
            df[col] = parsed
    return df, date_info


def _is_blank(series) -> Any:
    if series.dtype == object:
        return series.isna() | series.astype(str).str.strip().eq("")
    return series.isna()


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body])


def _render_html_from_md(md_text: str) -> str:
    escaped = _html.escape(md_text)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fuel Prices CSV Audit</title>
  <style>
    body {{ font-family: "Fira Sans", "Avenir Next", "Segoe UI", sans-serif; background: #f8f9fa; color: #222; padding: 18px; }}
    .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
    pre {{ white-space: pre-wrap; word-wrap: break-word; font-size: 0.9em; }}
  </style>
</head>
<body>
  <div class="card">
    <pre>{escaped}</pre>
  </div>
</body>
</html>
"""


def audit_csvs(format: str = "md") -> dict[str, Path]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for audit_csv") from exc

    from .constants import DATA_DIR, COLUMNS

    required_cols = set(COLUMNS)
    critical_cols = [
        "country",
        "fuel_product",
        "price_local",
        "currency",
        "unit",
        "source_key",
        "observation_date",
    ]

    report_lines: list[str] = []
    report_lines.append("# Fuel prices per-source audit")
    report_lines.append("")
    report_lines.append(f"Generated: {date.today().isoformat()}")
    report_lines.append("")

    summary_rows: list[list[str]] = []
    total_files = 0
    total_rows = 0

    obs_files = sorted(DATA_DIR.rglob("observations.csv"))

    for path in obs_files:
        rel_path = path.relative_to(DATA_DIR)
        label = str(rel_path.parent)

        df, date_info = _read_csv(path)
        n_rows = len(df)
        n_cols = len(df.columns)
        total_files += 1
        total_rows += n_rows

        missing_required = sorted(required_cols - set(df.columns))

        summary_rows.append(
            [label, str(n_rows), str(n_cols), str(len(missing_required))]
        )

        report_lines.append(f"## {label}")
        report_lines.append("")
        report_lines.append(f"Path: `{path}`")
        report_lines.append("")

        report_lines.append("### Schema checks")
        if missing_required:
            report_lines.append(
                f"- Missing required columns ({len(missing_required)}): {', '.join(missing_required)}"
            )
        else:
            report_lines.append("- Missing required columns: none")
        report_lines.append("")

        report_lines.append("### Nulls in critical fields")
        null_rows: list[list[str]] = []
        for col in critical_cols:
            if col in df.columns:
                blanks = int(_is_blank(df[col]).sum())
                null_rows.append([col, str(blanks)])
        report_lines.append(
            _table(["field", "blank_count"], null_rows) or "- No critical fields found"
        )
        report_lines.append("")

        report_lines.append("### Duplicate checks")
        dup_rows: list[list[str]] = []
        if "observation_hash" in df.columns:
            dup_hash = int(df["observation_hash"].duplicated(keep=False).sum())
            dup_rows.append(["observation_hash", str(dup_hash)])
        key_cols = [
            c
            for c in [
                "source_key",
                "observation_date",
                "fuel_product",
                "subnational_area",
                "city",
            ]
            if c in df.columns
        ]
        if key_cols:
            dup_keys = int(df.duplicated(subset=key_cols, keep=False).sum())
            dup_rows.append([" | ".join(key_cols), str(dup_keys)])
        report_lines.append(
            _table(["key", "duplicate_rows"], dup_rows)
            or "- No duplicate checks available"
        )
        report_lines.append("")

        report_lines.append("### Date checks")
        date_rows: list[list[str]] = []
        if "observation_date" in df.columns:
            obs = df["observation_date"]
            date_rows.append(
                [
                    "observation_date_min",
                    str(obs.min().date()) if obs.notna().any() else "—",
                ]
            )
            date_rows.append(
                [
                    "observation_date_max",
                    str(obs.max().date()) if obs.notna().any() else "—",
                ]
            )
            future = int((obs.notna() & (obs.dt.date > date.today())).sum())
            date_rows.append(["observation_date_future", str(future)])
        for col, info in date_info.items():
            date_rows.append([f"{col}_invalid", str(info["invalid"])])
            date_rows.append([f"{col}_missing", str(info["missing"])])

        report_lines.append(
            _table(["check", "count"], date_rows) or "- No date columns found"
        )
        report_lines.append("")

        report_lines.append("### Range checks")
        range_rows: list[list[str]] = []

        if "price_local" in df.columns:
            prices = pd.to_numeric(df["price_local"], errors="coerce")
            range_rows.append(["price_local_min", str(prices.min())])
            range_rows.append(["price_local_max", str(prices.max())])
            range_rows.append(
                ["price_local_nonpositive", str(int((prices <= 0).sum()))]
            )
            range_rows.append(["price_local_gt_1000", str(int((prices > 1000).sum()))])

        if "octane_ron" in df.columns:
            octane = pd.to_numeric(df["octane_ron"], errors="coerce")
            range_rows.append(
                [
                    "octane_ron_outside_70_110",
                    str(int(((octane < 70) | (octane > 110)).sum())),
                ]
            )

        if "ethanol_pct" in df.columns:
            ethanol = pd.to_numeric(df["ethanol_pct"], errors="coerce")
            range_rows.append(
                [
                    "ethanol_pct_outside_0_100",
                    str(int(((ethanol < 0) | (ethanol > 100)).sum())),
                ]
            )

        if "sulfur_standard" in df.columns:
            sulfur = pd.to_numeric(df["sulfur_standard"], errors="coerce")
            range_rows.append(
                ["sulfur_standard_negative", str(int((sulfur < 0).sum()))]
            )

        report_lines.append(
            _table(["check", "count"], range_rows) or "- No numeric ranges checked"
        )
        report_lines.append("")

    report_lines.insert(4, "## Summary")
    report_lines.insert(
        5,
        f"Audited **{total_files}** per-source observation files, **{total_rows:,}** total rows.\n\n"
        + _table(["source", "rows", "columns", "missing_required"], summary_rows),
    )
    report_lines.insert(6, "")

    md_text = "\n".join(report_lines).strip() + "\n"

    outputs: dict[str, Path] = {}
    md_path = DATA_DIR / "audit_report.md"
    md_path.write_text(md_text, encoding="utf-8")
    outputs["md"] = md_path

    if format in {"html", "both"}:
        html_path = DATA_DIR / "audit_report.html"
        html_path.write_text(_render_html_from_md(md_text), encoding="utf-8")
        outputs["html"] = html_path

    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit fuel price per-source data quality"
    )
    parser.add_argument(
        "--format",
        choices=["md", "html", "both"],
        default="md",
        help="Output format (default: md)",
    )
    args = parser.parse_args()
    outputs = audit_csvs(format=args.format)
    for kind, path in outputs.items():
        print(f"[audit] wrote {kind}: {path}")


if __name__ == "__main__":
    main()
