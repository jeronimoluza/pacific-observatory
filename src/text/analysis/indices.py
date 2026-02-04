"""
Extended Index Calculation Module

Provides shared standardization, aggregation, and normalization logic
for all index types (breadth, intensity, pairwise).

Index Types:
- Marginal Breadth: E_breadth, P_breadth, U_breadth = X_count / A_total
- Marginal Intensity: E_intensity, P_intensity, U_intensity = X_kwsum / X_count
- Pairwise Interaction: EU_share, PU_share, EP_share = XY_count / A_total

All indices follow the same pipeline:
1. Calculate raw ratio per source
2. Standardize (z-score using cutoff period std)
3. Aggregate across sources (weighted and unweighted)
4. Normalize to mean=100 over cutoff period
"""

from typing import List
import pandas as pd
import numpy as np


class IndexCalculator:
    """Calculates standardized indices following EPU methodology."""

    def __init__(self, cutoff: str):
        """
        Initialize the IndexCalculator.

        Args:
            cutoff: Date string for standardization period (e.g., '2020-12-31').
        """
        self.cutoff = cutoff

    def calculate_breadth_indices(
        self, epu_stats: pd.DataFrame, sources: List[str]
    ) -> pd.DataFrame:
        """
        Calculate E_breadth, P_breadth, U_breadth for all sources.

        Breadth = X_count / A_total (proportion of articles containing category X)

        Args:
            epu_stats: DataFrame with per-source counts.
            sources: List of source names.

        Returns:
            DataFrame with breadth index columns added.
        """
        # Defragment DataFrame to avoid performance warnings
        epu_stats = epu_stats.copy()

        for category in ["E", "P", "U"]:
            # Calculate raw ratio per source
            ratio_cols = []
            for source in sources:
                count_col = f"{source}_{category}_count"
                total_col = f"{source}_A_total"
                ratio_col = f"{source}_{category}_breadth_ratio"

                if count_col in epu_stats.columns and total_col in epu_stats.columns:
                    epu_stats[ratio_col] = epu_stats[count_col] / epu_stats[total_col]
                    epu_stats[ratio_col] = epu_stats[ratio_col].replace(
                        [np.inf, -np.inf], np.nan
                    )
                    ratio_cols.append(ratio_col)

            if ratio_cols:
                # Standardize, aggregate, normalize
                epu_stats = self._standardize_aggregate_normalize(
                    epu_stats,
                    ratio_cols,
                    sources,
                    f"{category}_breadth",
                )

        return epu_stats

    def calculate_intensity_indices(
        self, epu_stats: pd.DataFrame, sources: List[str]
    ) -> pd.DataFrame:
        """
        Calculate E_intensity, P_intensity, U_intensity for all sources.

        Intensity = X_kwsum / X_count (average keywords per article with category X)

        Args:
            epu_stats: DataFrame with per-source counts.
            sources: List of source names.

        Returns:
            DataFrame with intensity index columns added.
        """
        # Defragment DataFrame to avoid performance warnings
        epu_stats = epu_stats.copy()

        for category in ["E", "P", "U"]:
            # Calculate raw ratio per source
            ratio_cols = []
            for source in sources:
                kwsum_col = f"{source}_{category}_kwsum"
                count_col = f"{source}_{category}_count"
                ratio_col = f"{source}_{category}_intensity_ratio"

                if kwsum_col in epu_stats.columns and count_col in epu_stats.columns:
                    epu_stats[ratio_col] = epu_stats[kwsum_col] / epu_stats[count_col]
                    epu_stats[ratio_col] = epu_stats[ratio_col].replace(
                        [np.inf, -np.inf], np.nan
                    )
                    ratio_cols.append(ratio_col)

            if ratio_cols:
                # Standardize, aggregate, normalize
                epu_stats = self._standardize_aggregate_normalize(
                    epu_stats,
                    ratio_cols,
                    sources,
                    f"{category}_intensity",
                )

        return epu_stats

    def calculate_pairwise_indices(
        self, epu_stats: pd.DataFrame, sources: List[str]
    ) -> pd.DataFrame:
        """
        Calculate EU_share, PU_share, EP_share for all sources.

        Pairwise = XY_count / A_total (proportion of articles with both X and Y)

        Args:
            epu_stats: DataFrame with per-source counts.
            sources: List of source names.

        Returns:
            DataFrame with pairwise index columns added.
        """
        # Defragment DataFrame to avoid performance warnings
        epu_stats = epu_stats.copy()

        for pair in ["EU", "PU", "EP"]:
            # Calculate raw ratio per source
            ratio_cols = []
            for source in sources:
                count_col = f"{source}_{pair}_count"
                total_col = f"{source}_A_total"
                ratio_col = f"{source}_{pair}_share_ratio"

                if count_col in epu_stats.columns and total_col in epu_stats.columns:
                    epu_stats[ratio_col] = epu_stats[count_col] / epu_stats[total_col]
                    epu_stats[ratio_col] = epu_stats[ratio_col].replace(
                        [np.inf, -np.inf], np.nan
                    )
                    ratio_cols.append(ratio_col)

            if ratio_cols:
                # Standardize, aggregate, normalize
                epu_stats = self._standardize_aggregate_normalize(
                    epu_stats,
                    ratio_cols,
                    sources,
                    f"{pair}_share",
                )

        return epu_stats

    def _standardize_aggregate_normalize(
        self,
        df: pd.DataFrame,
        ratio_cols: List[str],
        sources: List[str],
        index_name: str,
    ) -> pd.DataFrame:
        """
        Apply standardization, aggregation, and normalization pipeline.

        Args:
            df: DataFrame with ratio columns.
            ratio_cols: List of ratio column names.
            sources: List of source names.
            index_name: Name for the output index (e.g., 'E_breadth').

        Returns:
            DataFrame with standardized, aggregated, and normalized columns.
        """
        # Standardize each ratio column
        z_cols = []
        for ratio_col in ratio_cols:
            z_col = ratio_col.replace("_ratio", "_z")
            df = self._standardize(df, ratio_col, z_col)
            z_cols.append(z_col)

        # Aggregate across sources
        df = self._aggregate(df, z_cols, sources, index_name)

        # Normalize to mean=100
        df = self._normalize(df, f"{index_name}_z_weighted", f"{index_name}_weighted")
        df = self._normalize(
            df, f"{index_name}_z_unweighted", f"{index_name}_unweighted"
        )

        return df

    def _standardize(
        self, df: pd.DataFrame, ratio_col: str, z_col: str
    ) -> pd.DataFrame:
        """
        Apply z-score standardization using cutoff period.

        Args:
            df: DataFrame with ratio column.
            ratio_col: Name of the ratio column to standardize.
            z_col: Name of the output z-score column.

        Returns:
            DataFrame with z-score column added.
        """
        if self.cutoff is not None:
            std = df[df["date"] < self.cutoff][ratio_col].std()
        else:
            std = df[ratio_col].std()

        if std == 0 or pd.isna(std):
            df[z_col] = np.nan
        else:
            df[z_col] = df[ratio_col] / std

        return df

    def _aggregate(
        self,
        df: pd.DataFrame,
        z_cols: List[str],
        sources: List[str],
        index_name: str,
    ) -> pd.DataFrame:
        """
        Aggregate across sources (weighted and unweighted mean).

        Args:
            df: DataFrame with z-score columns.
            z_cols: List of z-score column names.
            sources: List of source names.
            index_name: Name for the output index.

        Returns:
            DataFrame with aggregated z-score columns.
        """
        # Unweighted: simple mean
        df[f"{index_name}_z_unweighted"] = df[z_cols].mean(axis=1, skipna=True)

        # Weighted: use newspaper weights
        df[f"{index_name}_z_weighted"] = 0.0
        for z_col in z_cols:
            # Extract source name from z_col (format: {source}_{category}_{type}_z)
            parts = z_col.rsplit("_", 3)  # Split from right
            source = parts[0]
            weight_col = f"{source}_weights"

            if weight_col in df.columns:
                contribution = df[weight_col] * df[z_col]
                contribution = contribution.fillna(0)
                df[f"{index_name}_z_weighted"] += contribution

        return df

    def _normalize(
        self, df: pd.DataFrame, z_col: str, output_name: str
    ) -> pd.DataFrame:
        """
        Normalize to mean=100 over cutoff period.

        Args:
            df: DataFrame with z-score column.
            z_col: Name of the z-score column.
            output_name: Name of the output normalized column.

        Returns:
            DataFrame with normalized column added.
        """
        if self.cutoff is not None:
            mean_val = df[df["date"] < self.cutoff][z_col].mean()
        else:
            mean_val = df[z_col].mean()

        if mean_val == 0 or pd.isna(mean_val):
            df[output_name] = np.nan
        else:
            scaling_factor = 100 / mean_val
            df[output_name] = scaling_factor * df[z_col]

        return df
