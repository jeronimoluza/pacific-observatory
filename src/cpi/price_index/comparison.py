"""
Comparison Module for CPI Construction.

Compare constructed CPI indices with IMF official CPI data.
Calculate inflation rates (MoM, YoY) and validation metrics.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from scipy import stats
import sdmx


def fetch_imf_cpi(
    country_code: str = "FJI",
    coicop_code: str = "CP01",
    start_period: str = "2024",
    end_period: str = "2026",
) -> pd.DataFrame:
    """
    Fetch CPI data from IMF using SDMX.

    Args:
        country_code: ISO 3-letter country code (e.g., 'FJI' for Fiji)
        coicop_code: COICOP code (e.g., 'CP01' for Division 01)
        start_period: Start year for data retrieval (default: 2024)
        end_period: End year for data retrieval (default: 2026)

    Returns:
        DataFrame with columns: month, imf_index
    """
    print(
        f"Fetching IMF CPI data for {country_code}, {coicop_code} ({start_period}-{end_period})..."
    )

    # Initialize SDMX client
    IMF_DATA = sdmx.Client("IMF_DATA")

    # Fetch data
    # Key format: COUNTRY.INDEX_TYPE.COICOP.TYPE_OF_TRANSFORMATION.FREQUENCY
    key = f"{country_code}.CPI.{coicop_code}.IX.M"
    data_msg = IMF_DATA.data(
        "CPI", key=key, params={"startPeriod": start_period, "endPeriod": end_period}
    )

    # Convert to pandas
    cpi_series = sdmx.to_pandas(data_msg)

    # Create DataFrame
    df = pd.DataFrame({"imf_index": cpi_series})
    df = df.reset_index()

    # Parse TIME_PERIOD (format: YYYY-MXX where XX is month number)
    # Convert to YYYY-MM format to match constructed CPI
    df["TIME_PERIOD"] = df["TIME_PERIOD"].astype(str)

    # Extract year and month, handle format like "2025-M01" or "2025-M1"
    df["year"] = df["TIME_PERIOD"].str[:4]
    df["month_num"] = df["TIME_PERIOD"].str.split("-M").str[1].str.zfill(2)
    df["month"] = df["year"] + "-" + df["month_num"]

    # Select relevant columns
    df = df[["month", "imf_index"]].copy()

    print(f"  - Fetched {len(df)} months of IMF data")
    print(f"  - Period: {df['month'].min()} to {df['month'].max()}")

    return df


def load_constructed_cpi(
    filepath: str | Path,
    country: str = "fiji",
) -> pd.DataFrame:
    """
    Load constructed CPI from output file.

    Args:
        filepath: Path to Division 01 CPI CSV file
        country: Country name (for validation)

    Returns:
        DataFrame with columns: month, constructed_index
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(
            f"Constructed CPI file not found: {filepath}\n"
            f"Run the CPI construction pipeline first."
        )

    print(f"Loading constructed CPI from {filepath}...")

    df = pd.read_csv(filepath)

    # Validate
    if "month" not in df.columns or "cpi_index" not in df.columns:
        raise ValueError(
            "Expected columns 'month' and 'cpi_index' in constructed CPI file"
        )

    # Select and rename
    df = df[["month", "cpi_index"]].copy()
    df = df.rename(columns={"cpi_index": "constructed_index"})

    print(f"  - Loaded {len(df)} months of constructed CPI")
    print(f"  - Period: {df['month'].min()} to {df['month'].max()}")

    return df


def calculate_inflation(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    """
    Calculate MoM and YoY inflation rates.

    Args:
        df: DataFrame with month and index columns
        index_col: Name of the index column

    Returns:
        DataFrame with added inflation columns
    """
    df = df.copy()
    df = df.sort_values("month")

    # Month-over-month (MoM) inflation
    df[f"{index_col}_mom"] = (df[index_col] / df[index_col].shift(1) - 1) * 100

    # Year-over-year (YoY) inflation
    df[f"{index_col}_yoy"] = (df[index_col] / df[index_col].shift(12) - 1) * 100

    return df


def compute_metrics(
    df: pd.DataFrame,
    constructed_col: str = "constructed_index_mom",
    imf_col: str = "imf_index_mom",
) -> dict:
    """
    Compute validation metrics between constructed and IMF CPI.

    Metrics:
    - Pearson correlation
    - RMSE (Root Mean Squared Error)
    - Bias (Mean Error)
    - MAE (Mean Absolute Error)

    Args:
        df: DataFrame with both constructed and IMF inflation rates
        constructed_col: Column name for constructed inflation
        imf_col: Column name for IMF inflation

    Returns:
        Dictionary with metrics
    """
    # Filter to rows with both values
    valid = df[[constructed_col, imf_col]].dropna()

    if len(valid) == 0:
        return {
            "n_observations": 0,
            "pearson_correlation": np.nan,
            "p_value": np.nan,
            "rmse": np.nan,
            "bias": np.nan,
            "mae": np.nan,
        }

    constructed = valid[constructed_col].values
    imf = valid[imf_col].values

    # Pearson correlation
    corr, p_value = stats.pearsonr(constructed, imf)

    # RMSE
    rmse = np.sqrt(np.mean((constructed - imf) ** 2))

    # Bias (mean error)
    bias = np.mean(constructed - imf)

    # MAE (mean absolute error)
    mae = np.mean(np.abs(constructed - imf))

    return {
        "n_observations": len(valid),
        "pearson_correlation": corr,
        "p_value": p_value,
        "rmse": rmse,
        "bias": bias,
        "mae": mae,
    }


def compute_lead_lag_correlation(
    df: pd.DataFrame,
    constructed_col: str = "constructed_index_mom",
    imf_col: str = "imf_index_mom",
    max_lag: int = 2,
) -> dict:
    """
    Compute lead-lag correlation analysis with p-values.

    Tests if constructed CPI leads or lags IMF CPI by shifting one series.
    Negative lag = constructed leads IMF
    Positive lag = constructed lags IMF

    Args:
        df: DataFrame with both inflation rates
        constructed_col: Column name for constructed inflation
        imf_col: Column name for IMF inflation
        max_lag: Maximum lag to test (range: -max_lag to +max_lag)

    Returns:
        Dictionary with correlations and p-values at each lag
    """
    constructed = df[constructed_col].dropna()
    imf = df[imf_col].dropna()

    # Align to same index
    common_idx = constructed.index.intersection(imf.index)
    constructed = constructed.loc[common_idx]
    imf = imf.loc[common_idx]

    lead_lag_corr = {}
    for lag in range(-max_lag, max_lag + 1):
        try:
            # Get aligned data for this lag
            imf_shifted = imf.shift(lag)
            valid_mask = constructed.notna() & imf_shifted.notna()
            x = constructed[valid_mask].values
            y = imf_shifted[valid_mask].values

            # Calculate correlation and p-value
            corr, p_value = stats.pearsonr(x, y)
            lead_lag_corr[f"lag_{lag:+d}"] = {
                "correlation": corr,
                "p_value": p_value,
                "n_obs": valid_mask.sum(),
            }
        except Exception:
            lead_lag_corr[f"lag_{lag:+d}"] = {
                "correlation": np.nan,
                "p_value": np.nan,
                "n_obs": 0,
            }

    return lead_lag_corr


def compute_rolling_metrics(
    df: pd.DataFrame,
    constructed_col: str = "constructed_index_mom",
    imf_col: str = "imf_index_mom",
    window: int = 3,
) -> dict:
    """
    Compute validation metrics on rolling averages.

    Args:
        df: DataFrame with both inflation rates
        constructed_col: Column name for constructed inflation
        imf_col: Column name for IMF inflation
        window: Rolling window size (default: 3)

    Returns:
        Dictionary with metrics for rolling averages
    """
    df_rolling = df.copy()

    # Compute rolling means
    df_rolling[f"{constructed_col}_rolling"] = (
        df_rolling[constructed_col].rolling(window=window).mean()
    )
    df_rolling[f"{imf_col}_rolling"] = df_rolling[imf_col].rolling(window=window).mean()

    # Compute metrics on rolling data
    metrics = compute_metrics(
        df_rolling,
        constructed_col=f"{constructed_col}_rolling",
        imf_col=f"{imf_col}_rolling",
    )

    return metrics


def compare_cpi(
    constructed_filepath: str | Path,
    country_code: str = "FJI",
    coicop_code: str = "CP01",
    start_period: str = "2024",
    end_period: str = "2026",
    output_dir: Optional[str | Path] = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Compare constructed CPI with IMF official data (2024-2026).

    Args:
        constructed_filepath: Path to constructed Division 01 CPI CSV
        country_code: ISO 3-letter country code for IMF data
        coicop_code: COICOP code (e.g., 'CP01' for Division 01)
        start_period: Start year for IMF data (default: 2024)
        end_period: End year for IMF data (default: 2026)
        output_dir: Optional directory to save comparison results

    Returns:
        Tuple of (comparison DataFrame, metrics dict)
    """
    print("\n" + "=" * 70)
    print("CPI COMPARISON: CONSTRUCTED vs IMF (2024-2026)")
    print("=" * 70)

    # Load IMF data
    imf_df = fetch_imf_cpi(country_code, coicop_code, start_period, end_period)

    # Load constructed CPI
    constructed_df = load_constructed_cpi(constructed_filepath)

    # Merge
    df = pd.merge(imf_df, constructed_df, on="month", how="outer")
    df = df.sort_values("month")

    print(f"\nMerged data: {len(df)} months")
    print(f"  - IMF data available: {df['imf_index'].notna().sum()} months")
    print(
        f"  - Constructed data available: {df['constructed_index'].notna().sum()} months"
    )
    print(
        f"  - Overlap: {df[['imf_index', 'constructed_index']].notna().all(axis=1).sum()} months"
    )

    # Calculate inflation rates
    print("\nCalculating inflation rates...")
    df = calculate_inflation(df, "imf_index")
    df = calculate_inflation(df, "constructed_index")

    # Compute metrics (using MoM inflation)
    print("\nComputing validation metrics...")
    metrics_mom = compute_metrics(df, "constructed_index_mom", "imf_index_mom")
    metrics_yoy = compute_metrics(df, "constructed_index_yoy", "imf_index_yoy")
    metrics_rolling = compute_rolling_metrics(
        df, "constructed_index_mom", "imf_index_mom", window=3
    )
    lead_lag = compute_lead_lag_correlation(
        df, "constructed_index_mom", "imf_index_mom", max_lag=2
    )

    # Print MoM metrics
    print("\n" + "-" * 70)
    print("VALIDATION METRICS (Month-over-Month Inflation)")
    print("-" * 70)
    print(f"Observations: {metrics_mom['n_observations']}")
    print(f"Pearson Correlation: {metrics_mom['pearson_correlation']:.4f}")
    print(f"  p-value: {metrics_mom['p_value']:.4e}")
    print(f"RMSE: {metrics_mom['rmse']:.4f} percentage points")
    print(f"Bias (Mean Error): {metrics_mom['bias']:.4f} percentage points")
    print(f"MAE (Mean Absolute Error): {metrics_mom['mae']:.4f} percentage points")
    print("-" * 70)

    # Print YoY metrics
    print("\n" + "-" * 70)
    print("VALIDATION METRICS (Year-over-Year Inflation)")
    print("-" * 70)
    print(f"Observations: {metrics_yoy['n_observations']}")
    print(f"Pearson Correlation: {metrics_yoy['pearson_correlation']:.4f}")
    print(f"  p-value: {metrics_yoy['p_value']:.4e}")
    print(f"RMSE: {metrics_yoy['rmse']:.4f} percentage points")
    print(f"Bias (Mean Error): {metrics_yoy['bias']:.4f} percentage points")
    print(f"MAE (Mean Absolute Error): {metrics_yoy['mae']:.4f} percentage points")
    print("-" * 70)

    # Print rolling (3-month) metrics
    print("\n" + "-" * 70)
    print("VALIDATION METRICS (3-Month Rolling Average MoM Inflation)")
    print("-" * 70)
    print(f"Observations: {metrics_rolling['n_observations']}")
    print(f"Pearson Correlation: {metrics_rolling['pearson_correlation']:.4f}")
    print(f"  p-value: {metrics_rolling['p_value']:.4e}")
    print(f"RMSE: {metrics_rolling['rmse']:.4f} percentage points")
    print(f"Bias (Mean Error): {metrics_rolling['bias']:.4f} percentage points")
    print(f"MAE (Mean Absolute Error): {metrics_rolling['mae']:.4f} percentage points")
    print("-" * 70)

    # Print lead-lag analysis
    print("\n" + "-" * 70)
    print("LEAD-LAG CORRELATION ANALYSIS (MoM Inflation)")
    print("(Negative lag = Constructed leads IMF, Positive lag = Constructed lags IMF)")
    print("-" * 70)
    for lag_key in sorted(lead_lag.keys(), key=lambda x: int(x.split("_")[1])):
        lag_data = lead_lag[lag_key]
        corr = lag_data["correlation"]
        p_val = lag_data["p_value"]
        n_obs = lag_data["n_obs"]
        lag_val = int(lag_key.split("_")[1])
        if lag_val < 0:
            direction = "leads"
        elif lag_val > 0:
            direction = "lags"
        else:
            direction = "synchronous"
        print(f"  {lag_key}: {corr:+.4f} (p-value: {p_val:.4e}, n={n_obs})")
        print(
            f"           Constructed {direction} IMF by {abs(lag_val)} month{'s' if abs(lag_val) != 1 else ''}"
        )
    print("-" * 70)

    # Export if output directory specified
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export comparison data
        comparison_file = output_dir / "cpi_comparison.csv"
        df.to_csv(comparison_file, index=False)
        print(f"\nExported comparison data: {comparison_file}")

        # Export metrics
        metrics_file = output_dir / "comparison_metrics.txt"
        with open(metrics_file, "w") as f:
            f.write("CPI COMPARISON METRICS (2024-2026)\n")
            f.write("=" * 70 + "\n")
            f.write(f"Country: {country_code}\n")
            f.write(f"COICOP: {coicop_code}\n")

            # MoM metrics
            f.write("\nValidation Metrics (Month-over-Month Inflation):\n")
            f.write("-" * 70 + "\n")
            f.write(f"Observations: {metrics_mom['n_observations']}\n")
            f.write(f"Pearson Correlation: {metrics_mom['pearson_correlation']:.4f}\n")
            f.write(f"  p-value: {metrics_mom['p_value']:.4e}\n")
            f.write(f"RMSE: {metrics_mom['rmse']:.4f} percentage points\n")
            f.write(f"Bias (Mean Error): {metrics_mom['bias']:.4f} percentage points\n")
            f.write(f"MAE: {metrics_mom['mae']:.4f} percentage points\n")

            # YoY metrics
            f.write("\nValidation Metrics (Year-over-Year Inflation):\n")
            f.write("-" * 70 + "\n")
            f.write(f"Observations: {metrics_yoy['n_observations']}\n")
            f.write(f"Pearson Correlation: {metrics_yoy['pearson_correlation']:.4f}\n")
            f.write(f"  p-value: {metrics_yoy['p_value']:.4e}\n")
            f.write(f"RMSE: {metrics_yoy['rmse']:.4f} percentage points\n")
            f.write(f"Bias (Mean Error): {metrics_yoy['bias']:.4f} percentage points\n")
            f.write(f"MAE: {metrics_yoy['mae']:.4f} percentage points\n")

            # Rolling metrics
            f.write("\nValidation Metrics (3-Month Rolling Average MoM Inflation):\n")
            f.write("-" * 70 + "\n")
            f.write(f"Observations: {metrics_rolling['n_observations']}\n")
            f.write(
                f"Pearson Correlation: {metrics_rolling['pearson_correlation']:.4f}\n"
            )
            f.write(f"  p-value: {metrics_rolling['p_value']:.4e}\n")
            f.write(f"RMSE: {metrics_rolling['rmse']:.4f} percentage points\n")
            f.write(
                f"Bias (Mean Error): {metrics_rolling['bias']:.4f} percentage points\n"
            )
            f.write(f"MAE: {metrics_rolling['mae']:.4f} percentage points\n")

            # Lead-lag analysis
            f.write("\nLead-Lag Correlation Analysis (MoM Inflation):\n")
            f.write(
                "(Negative lag = Constructed leads IMF, Positive lag = Constructed lags IMF)\n"
            )
            f.write("-" * 70 + "\n")
            for lag_key in sorted(lead_lag.keys(), key=lambda x: int(x.split("_")[1])):
                lag_data = lead_lag[lag_key]
                corr = lag_data["correlation"]
                p_val = lag_data["p_value"]
                n_obs = lag_data["n_obs"]
                lag_val = int(lag_key.split("_")[1])
                if lag_val < 0:
                    direction = "leads"
                elif lag_val > 0:
                    direction = "lags"
                else:
                    direction = "synchronous"
                f.write(f"  {lag_key}: {corr:+.4f} (p-value: {p_val:.4e}, n={n_obs})\n")
                f.write(
                    f"           Constructed {direction} IMF by {abs(lag_val)} month{'s' if abs(lag_val) != 1 else ''}\n"
                )
        print(f"Exported metrics: {metrics_file}")

    print("=" * 70 + "\n")

    return df, metrics_mom


def main():
    """
    Main function for command-line usage.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare constructed CPI with IMF official data (2024-2026)"
    )
    parser.add_argument(
        "--constructed-cpi",
        type=str,
        default="data/cpi/analysis/output/fiji_division_01_cpi.csv",
        help="Path to constructed Division 01 CPI CSV",
    )
    parser.add_argument(
        "--country-code",
        type=str,
        default="FJI",
        help="ISO 3-letter country code for IMF data (default: FJI)",
    )
    parser.add_argument(
        "--coicop",
        type=str,
        default="CP01",
        help="COICOP code (default: CP01 for Division 01)",
    )
    parser.add_argument(
        "--start-period",
        type=str,
        default="2024",
        help="Start year for IMF data (default: 2024)",
    )
    parser.add_argument(
        "--end-period",
        type=str,
        default="2026",
        help="End year for IMF data (default: 2026)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/cpi/analysis/output",
        help="Output directory for comparison results",
    )

    args = parser.parse_args()

    # Run comparison
    df, metrics = compare_cpi(
        constructed_filepath=args.constructed_cpi,
        country_code=args.country_code,
        coicop_code=args.coicop,
        start_period=args.start_period,
        end_period=args.end_period,
        output_dir=args.output_dir,
    )

    # Add rolling averages to the dataframe for display
    df["imf_index_mom_rolling"] = df["imf_index_mom"].rolling(window=3).mean()
    df["constructed_index_mom_rolling"] = (
        df["constructed_index_mom"].rolling(window=3).mean()
    )

    # Print sample of comparison data
    print("\nSample comparison data (last 12 months):")
    print(
        df[
            [
                "month",
                "imf_index",
                "constructed_index",
                "imf_index_mom",
                "constructed_index_mom",
                "imf_index_mom_rolling",
                "constructed_index_mom_rolling",
            ]
        ].tail(12)
    )


if __name__ == "__main__":
    main()
