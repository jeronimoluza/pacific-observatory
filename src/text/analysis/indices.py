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

import warnings
from typing import List
import pandas as pd
import numpy as np

from src.text.analysis.baseline import baseline_mask

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings(
    "ignore", message="Mean of empty slice", category=RuntimeWarning
)


class IndexCalculator:
    """Calculates standardized indices following EPU methodology."""

    def __init__(self, cutoff_start_date: str | None, cutoff_end_date: str | None):
        """
        Initialize the IndexCalculator.

        Args:
            cutoff_start_date: Inclusive baseline start date.
            cutoff_end_date: Inclusive baseline end date.
        """
        self.cutoff_start_date = cutoff_start_date
        self.cutoff_end_date = cutoff_end_date
        self.stds: dict = {}
        self.scaling_factors: dict = {}

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

        Accumulates all new columns in a single dict and performs one
        pd.concat to avoid DataFrame fragmentation.

        Args:
            df: DataFrame with ratio columns.
            ratio_cols: List of ratio column names.
            sources: List of source names.
            index_name: Name for the output index (e.g., 'E_breadth').

        Returns:
            DataFrame with standardized, aggregated, and normalized columns.
        """
        z_cols = []

        # Standardize each ratio column
        for ratio_col in ratio_cols:
            z_col = ratio_col.replace("_ratio", "_z")
            z_series, std = self._standardize_series(df[ratio_col], df)
            df[z_col] = z_series.values
            self.stds[ratio_col] = std
            z_cols.append(z_col)

        # Aggregate (unweighted and weighted)
        df[f"{index_name}_z_unweighted"] = df[z_cols].mean(axis=1, skipna=True)

        weighted = np.zeros(len(df))
        for z_col in z_cols:
            source = next((s for s in sources if z_col.startswith(f"{s}_")), None)
            if source is None:
                continue
            weight_col = f"{source}_weights"
            if weight_col in df.columns:
                weighted += np.nan_to_num(df[weight_col].values * df[z_col].values)
        df[f"{index_name}_z_weighted"] = weighted

        # Normalize to mean=100
        for z_col_name, out_name in [
            (f"{index_name}_z_weighted", f"{index_name}_weighted"),
            (f"{index_name}_z_unweighted", f"{index_name}_unweighted"),
        ]:
            z_arr = df[z_col_name].values
            mask = baseline_mask(
                df["date"], self.cutoff_start_date, self.cutoff_end_date
            ).to_numpy()
            sub = z_arr[mask]
            mean_val = (
                np.nanmean(sub)
                if len(sub) > 0 and not np.all(np.isnan(sub))
                else np.nan
            )
            if np.isnan(mean_val) or mean_val == 0:
                df[out_name] = np.nan
                scaling_factor = None
            else:
                scaling_factor = 100 / mean_val
                df[out_name] = scaling_factor * z_arr
            self.scaling_factors[out_name] = (
                float(scaling_factor) if scaling_factor is not None else None
            )

        return df

    def _standardize_series(self, ratio_series: pd.Series, df: pd.DataFrame):
        """
        Compute z-score Series for a ratio column using the cutoff period std.

        Returns:
            Tuple of (z_series, std_float_or_None).
        """
        std = ratio_series[
            baseline_mask(df["date"], self.cutoff_start_date, self.cutoff_end_date)
        ].std()

        if std == 0 or pd.isna(std):
            return pd.Series(np.nan, index=ratio_series.index), None
        return ratio_series / std, float(std)

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
        std = df.loc[
            baseline_mask(df["date"], self.cutoff_start_date, self.cutoff_end_date),
            ratio_col,
        ].std()

        if std == 0 or pd.isna(std):
            df[z_col] = np.nan
        else:
            df[z_col] = df[ratio_col] / std

        self.stds[ratio_col] = float(std) if not pd.isna(std) else None
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
            # Extract source name by matching against known sources
            source = None
            for s in sources:
                if z_col.startswith(f"{s}_"):
                    source = s
                    break
            if source is None:
                continue
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
        mean_val = df.loc[
            baseline_mask(df["date"], self.cutoff_start_date, self.cutoff_end_date),
            z_col,
        ].mean()

        if mean_val == 0 or pd.isna(mean_val):
            df[output_name] = np.nan
            scaling_factor = None
        else:
            scaling_factor = 100 / mean_val
            df[output_name] = scaling_factor * df[z_col]

        self.scaling_factors[output_name] = (
            float(scaling_factor) if scaling_factor is not None else None
        )
        return df

    def get_params(self) -> dict:
        """
        Return captured standardization parameters.

        Returns:
            Dict with 'ratio_stds' and 'scaling_factors' collected during computation.
        """
        return {
            "ratio_stds": dict(self.stds),
            "scaling_factors": dict(self.scaling_factors),
        }

    def calculate_absolute_uncertainty_attribution(
        self,
        df: pd.DataFrame,
        sources: List[str],
        group_names: List[str],
    ) -> pd.DataFrame:
        """
        Calculate absolute uncertainty attribution: (U ∩ G) / A per group.

        Args:
            df: DataFrame with per-source UG counts and A_total.
            sources: List of source names.
            group_names: List of group names.

        Returns:
            DataFrame with {group}_absolute_weighted columns added.
        """
        df = df.copy()
        for g in group_names:
            ratio_cols = []
            for source in sources:
                ug_col = f"{source}_UG_{g}_count"
                total_col = f"{source}_A_total"
                ratio_col = f"{source}_UG_{g}_abs_ratio"
                if ug_col in df.columns and total_col in df.columns:
                    df[ratio_col] = df[ug_col] / df[total_col]
                    df[ratio_col] = df[ratio_col].replace([np.inf, -np.inf], np.nan)
                    ratio_cols.append(ratio_col)
            if ratio_cols:
                df = self._standardize_aggregate_normalize(
                    df, ratio_cols, sources, f"UG_{g}_abs"
                )
        return df

    def calculate_topic_intensity_attribution(
        self,
        df: pd.DataFrame,
        sources: List[str],
        group_names: List[str],
    ) -> pd.DataFrame:
        """
        Calculate unconditional topic intensity: G / A per group.

        This is the only group index that does not condition on uncertainty. It
        answers "how much is this topic being discussed", where
        `calculate_absolute_uncertainty_attribution` answers "how much of the
        discussion is both about this topic and uncertain". A topic can be
        heavily covered and rarely uncertain, so the two series are not
        rescalings of each other.

        Args:
            df: DataFrame with per-source G counts and A_total.
            sources: List of source names.
            group_names: List of group names.

        Returns:
            DataFrame with {group}_int_weighted columns added.
        """
        df = df.copy()
        for g in group_names:
            ratio_cols = []
            for source in sources:
                g_col = f"{source}_G_{g}_count"
                total_col = f"{source}_A_total"
                ratio_col = f"{source}_G_{g}_int_ratio"
                if g_col in df.columns and total_col in df.columns:
                    df[ratio_col] = df[g_col] / df[total_col]
                    df[ratio_col] = df[ratio_col].replace([np.inf, -np.inf], np.nan)
                    ratio_cols.append(ratio_col)
            if ratio_cols:
                df = self._standardize_aggregate_normalize(
                    df, ratio_cols, sources, f"G_{g}_int"
                )
        return df

    def calculate_framing_uncertainty_attribution(
        self,
        df: pd.DataFrame,
        sources: List[str],
        group_names: List[str],
    ) -> pd.DataFrame:
        """
        Calculate framing uncertainty attribution: (U ∩ G) / U per group.

        Args:
            df: DataFrame with per-source UG counts and U_count.
            sources: List of source names.
            group_names: List of group names.

        Returns:
            DataFrame with {group}_framing_weighted columns added.
        """
        df = df.copy()
        for g in group_names:
            ratio_cols = []
            for source in sources:
                ug_col = f"{source}_UG_{g}_count"
                u_col = f"{source}_U_count"
                ratio_col = f"{source}_UG_{g}_frm_ratio"
                if ug_col in df.columns and u_col in df.columns:
                    df[ratio_col] = df[ug_col] / df[u_col]
                    df[ratio_col] = df[ratio_col].replace([np.inf, -np.inf], np.nan)
                    ratio_cols.append(ratio_col)
            if ratio_cols:
                df = self._standardize_aggregate_normalize(
                    df, ratio_cols, sources, f"UG_{g}_frm"
                )
        return df
