"""OCR-focused audit for fuel price data quality.

Checks:
  1. forward_filled rows by source (shows contamination counts)
  2. Missing expected monthly periods per OCR source
  3. Partial extractions (fewer than expected products per month)
  4. Suspicious price repetition across consecutive months
  5. Out-of-range prices per source
  6. Price outliers (z-score > 3 within source×product)

Run directly::

    poetry run python -m src.cpi.fuel_prices.audit_ocr

Exits non-zero if any errors are found above the warning threshold.
Writes report to data/cpi/fuel_prices/ocr_audit_report.md
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

from .constants import DATA_DIR


# ---------------------------------------------------------------------------
# OCR source definitions — (source_key, expected_products, price_range, freq)
# ---------------------------------------------------------------------------
_OCR_SOURCES: list[tuple[str, int, tuple[float, float], str]] = [
    # Samoa: 3 products (petrol/diesel/kerosene), monthly, WST 1–15/L
    ("ws_mof_monthly_fuel_prices", 3, (1.0, 15.0), "monthly"),
    # Tonga: 3 products (petrol/diesel/kerosene), monthly, TOP 2–8/L
    ("to_mted_petroleum_prices_monthly", 3, (2.0, 8.0), "monthly"),
    # Vietnam: add here if OCR-sourced in future
]

# Number of consecutive months with identical prices to flag as suspicious
_REPEAT_THRESHOLD = 3

# Out-of-range check: any price outside [low, high] is flagged
# (separate from _OCR_SOURCES — covers all sources in the primary CSV)
_GLOBAL_PRICE_RANGE = (0.01, 999.0)


def _load_primary() -> pd.DataFrame:
    from .process import load_stored_observations

    df = load_stored_observations(DATA_DIR)
    if df.empty:
        raise FileNotFoundError(f"No per-source observations found under {DATA_DIR}")
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    return df


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No findings._\n"
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body]) + "\n"


# ---------------------------------------------------------------------------
# Check 1: forward_filled contamination
# ---------------------------------------------------------------------------
def _check_forward_filled(df: pd.DataFrame) -> tuple[list[str], list[list[str]]]:
    """Return (issues, table_rows) for forward_filled rows by source."""
    ff = df[df["status"].str.contains("forward_filled", na=False)]
    rows: list[list[str]] = []
    issues: list[str] = []
    for sk, grp in ff.groupby("source_key"):
        count = len(grp)
        rows.append([str(sk), str(count)])
        issues.append(f"forward_filled: {sk} has {count} rows")
    return issues, rows


# ---------------------------------------------------------------------------
# Check 2: Missing expected monthly periods
# ---------------------------------------------------------------------------
def _check_missing_months(
    df: pd.DataFrame,
    source_key: str,
    expected_products: int,
) -> tuple[list[str], list[list[str]]]:
    """Find months where fewer products than expected were extracted."""
    src = df[df["source_key"] == source_key].copy()
    if src.empty:
        return [f"missing_months: {source_key} has no rows at all"], []

    # Focus on clean (non-forward_filled) rows
    src = src[~src["status"].str.contains("forward_filled", na=False)]

    # Group by year-month
    src["ym"] = src["observation_date"].dt.to_period("M")
    monthly = src.groupby("ym")["fuel_product"].nunique()

    rows: list[list[str]] = []
    issues: list[str] = []

    # Build expected range: from min month to current month
    if monthly.empty:
        return [f"missing_months: {source_key} — no clean rows"], []

    min_ym = monthly.index.min()
    max_ym = pd.Period(date.today(), freq="M")
    current = min_ym
    while current <= max_ym:
        count = monthly.get(current, 0)
        if count < expected_products:
            rows.append(
                [str(source_key), str(current), str(count), str(expected_products)]
            )
            issues.append(
                f"partial: {source_key} {current} has {count}/{expected_products} products"
            )
        current = current + 1

    return issues, rows


# ---------------------------------------------------------------------------
# Check 3: Suspicious price repetition
# ---------------------------------------------------------------------------
def _check_price_repetition(
    df: pd.DataFrame,
    source_key: str,
    threshold: int = _REPEAT_THRESHOLD,
) -> tuple[list[str], list[list[str]]]:
    """Flag product series where the same price repeats for >= threshold months."""
    src = df[
        (df["source_key"] == source_key)
        & (~df["status"].str.contains("forward_filled", na=False))
    ].copy()

    if src.empty:
        return [], []

    src = src.sort_values("observation_date")
    rows: list[list[str]] = []
    issues: list[str] = []

    for product, grp in src.groupby("fuel_product"):
        grp = grp.sort_values("observation_date").drop_duplicates("observation_date")
        prices = grp["price_local"].tolist()
        dates = grp["observation_date"].dt.strftime("%Y-%m").tolist()
        if len(prices) < threshold:
            continue
        # Count runs of identical consecutive prices
        run_len = 1
        for i in range(1, len(prices)):
            if prices[i] == prices[i - 1]:
                run_len += 1
                if run_len >= threshold:
                    rows.append(
                        [
                            source_key,
                            str(product),
                            dates[i - run_len + 1],
                            dates[i],
                            str(prices[i]),
                            str(run_len),
                        ]
                    )
                    issues.append(
                        f"repetition: {source_key}/{product} price={prices[i]} "
                        f"repeated {run_len}× from {dates[i - run_len + 1]}"
                    )
                    break  # report once per run
            else:
                run_len = 1

    return issues, rows


# ---------------------------------------------------------------------------
# Check 4: Out-of-range prices
# ---------------------------------------------------------------------------
def _check_price_range(
    df: pd.DataFrame,
    source_key: str,
    low: float,
    high: float,
) -> tuple[list[str], list[list[str]]]:
    """Flag prices outside [low, high] for a specific source."""
    src = df[df["source_key"] == source_key]
    bad = src[(src["price_local"] < low) | (src["price_local"] > high)]

    rows: list[list[str]] = []
    issues: list[str] = []
    for _, r in bad.iterrows():
        rows.append(
            [
                source_key,
                str(r.get("fuel_product", "")),
                str(r.get("observation_date", ""))[:10],
                f"{r['price_local']:.4f}",
                f"[{low}, {high}]",
            ]
        )
        issues.append(
            f"out_of_range: {source_key}/{r.get('fuel_product', '')} "
            f"{str(r.get('observation_date', ''))[:10]} price={r['price_local']:.4f}"
        )

    return issues, rows


# ---------------------------------------------------------------------------
# Check 5: Z-score outliers within source×product
# ---------------------------------------------------------------------------
def _check_zscore_outliers(
    df: pd.DataFrame,
    source_key: str,
    z_threshold: float = 3.0,
) -> tuple[list[str], list[list[str]]]:
    """Flag prices with |z-score| > z_threshold within source×product series."""
    src = df[(df["source_key"] == source_key) & df["price_local"].notna()].copy()

    if src.empty:
        return [], []

    rows: list[list[str]] = []
    issues: list[str] = []

    for product, grp in src.groupby("fuel_product"):
        prices = grp["price_local"].values
        if len(prices) < 4:
            continue
        mean = float(pd.Series(prices).mean())
        std = float(pd.Series(prices).std())
        if std == 0:
            continue
        for _, row in grp.iterrows():
            z = abs((row["price_local"] - mean) / std)
            if z > z_threshold:
                rows.append(
                    [
                        source_key,
                        str(product),
                        str(row["observation_date"])[:10],
                        f"{row['price_local']:.4f}",
                        f"{z:.2f}",
                    ]
                )
                issues.append(
                    f"outlier: {source_key}/{product} "
                    f"{str(row['observation_date'])[:10]} "
                    f"price={row['price_local']:.4f} z={z:.2f}"
                )

    return issues, rows


# ---------------------------------------------------------------------------
# Main audit runner
# ---------------------------------------------------------------------------
def run_audit(output_path: Path | None = None) -> tuple[list[str], str]:
    """Run all OCR audit checks. Returns (issue_list, markdown_report)."""
    df = _load_primary()
    all_issues: list[str] = []
    sections: list[str] = []

    today = date.today().isoformat()
    sections.append(f"# OCR Audit Report\n\nGenerated: {today}\n")
    sections.append(f"Data directory: `{DATA_DIR}`  \nTotal rows: {len(df):,}\n")

    # ---- Check 1: forward_filled ----------------------------------------
    ff_issues, ff_rows = _check_forward_filled(df)
    all_issues.extend(ff_issues)
    sections.append("## 1. Forward-filled rows by source\n")
    if ff_rows:
        sections.append(_table(["source_key", "forward_filled_count"], ff_rows))
        sections.append(
            f"\n> **{len(ff_rows)} source(s)** have forward-filled rows. "
            "Consider purging stale fill rows.\n"
        )
    else:
        sections.append("_No forward-filled rows found._\n")

    # ---- Checks 2–5: per OCR source -------------------------------------
    for source_key, expected_products, price_range, _freq in _OCR_SOURCES:
        sections.append(f"## Source: `{source_key}`\n")

        # Check 2: missing/partial months
        m_issues, m_rows = _check_missing_months(df, source_key, expected_products)
        all_issues.extend(m_issues)
        sections.append("### 2. Missing / partial months\n")
        sections.append(
            _table(
                ["source_key", "month", "products_found", "expected"],
                m_rows,
            )
        )

        # Check 3: price repetition
        r_issues, r_rows = _check_price_repetition(df, source_key)
        all_issues.extend(r_issues)
        sections.append("### 3. Suspicious price repetition\n")
        sections.append(
            _table(
                [
                    "source_key",
                    "product",
                    "from_month",
                    "to_month",
                    "price",
                    "run_length",
                ],
                r_rows,
            )
        )

        # Check 4: out-of-range
        lo, hi = price_range
        p_issues, p_rows = _check_price_range(df, source_key, lo, hi)
        all_issues.extend(p_issues)
        sections.append(f"### 4. Out-of-range prices (expected [{lo}, {hi}])\n")
        sections.append(
            _table(
                ["source_key", "product", "date", "price", "expected_range"],
                p_rows,
            )
        )

        # Check 5: z-score outliers
        z_issues, z_rows = _check_zscore_outliers(df, source_key)
        all_issues.extend(z_issues)
        sections.append("### 5. Z-score outliers (|z| > 3)\n")
        sections.append(
            _table(
                ["source_key", "product", "date", "price", "z_score"],
                z_rows,
            )
        )

    # ---- Summary --------------------------------------------------------
    sections.append("## Summary\n")
    if all_issues:
        sections.append(f"**{len(all_issues)} issue(s) found:**\n")
        sections.append("\n".join(f"- {i}" for i in all_issues) + "\n")
    else:
        sections.append("**No issues found.** Data looks clean.\n")

    report = "\n".join(sections)

    if output_path is None:
        output_path = DATA_DIR / "ocr_audit_report.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"  [audit_ocr] Report written to {output_path}")

    return all_issues, report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="OCR data quality audit for fuel price CSVs"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for the markdown report (default: data/cpi/fuel_prices/ocr_audit_report.md)",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Exit 0 even if issues are found (warn but don't fail)",
    )
    args = parser.parse_args(argv)

    issues, _report = run_audit(output_path=args.output)

    if issues:
        print(f"\n[audit_ocr] {len(issues)} issue(s) found:")
        for iss in issues:
            print(f"  - {iss}")
        if args.warn_only:
            print("[audit_ocr] --warn-only: exiting 0 despite issues.")
            return 0
        return 1
    else:
        print("[audit_ocr] No issues found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
