"""
Economic Policy Uncertainty (EPU) Index Calculation Module

METHODOLOGY OVERVIEW
====================

This module implements the EPU index calculation methodology as follows:

1. RATIO CALCULATION (X_it):
   - For each newspaper i at time t, calculate the proportion of EPU news:
     X_it = (EPU news count in newspaper i at time t) / (All scraped news in newspaper i at time t)
   - Implemented in: calculate_ratios() method
   - Zero-division handling: Ratios with zero denominator result in NaN, which are handled downstream

2. STANDARDIZATION (Y_it):
   - Define T_1 as the standardization period (specified by 'cutoff' parameter)
   - Calculate standard deviation σ_i for each newspaper i over period T_1
   - Standardize X_it by dividing by σ_i: Y_it = X_it / σ_i
   - Implemented in: _calculate_z_score() method
   - Zero-division handling: If σ_i = 0 (no variation in data), Y_it is set to NaN instead of inf

3. MEAN AGGREGATION (Z_t):
   - Compute the mean of Y_it across all newspapers for each month:
     Z_t = mean(Y_it) at time t
   - Implemented in: _calculate_z_score() method (z_score_unweighted)
   - Zero-division handling: Uses skipna=True to ignore NaN values when computing mean

4. NORMALIZATION (EPU Index):
   - Calculate M = mean(Z_t) over the standardization period T_1
   - Normalize by multiplying Z_t by (100 / M) for all time periods
   - This ensures the EPU index has a mean of 100 over T_1
   - Implemented in: calculate_epu_score() method
   - Zero-division handling: If M = 0, scaling_factor becomes inf; protected by checking M != 0

WEIGHTED VARIANT:
   - Instead of simple mean, uses newspaper-specific weights (proportion of total news)
   - Z_t_weighted = sum(weight_i * Y_it) for each newspaper i
   - Implemented in: _calculate_z_score() method (z_score_weighted)

KEY FEATURES:
   - Handles multiple newspapers/sources simultaneously
   - Supports additional term categories for specialized EPU indices (e.g., inflation-specific)
   - Provides both weighted and unweighted EPU indices
   - Robust NaN handling throughout the pipeline

Last modified:
    2025-11-12

"""

import os
from typing import List, Union, Dict
import pandas as pd
import numpy as np
from .baseline import baseline_mask
from .utils import (
    match_keywords,
    load_topics_words,
    collapse_to_index_grid,
)

# Default English topic words (loaded at module level for backward compatibility)
_topics_data = load_topics_words(language="en")
ECON_LIST = _topics_data["economic"]
POLICY_LIST = _topics_data["policy"]
UNCERTAINTY_LIST = _topics_data["uncertainty"]


def get_terms_for_language(language: str = "en") -> Dict[str, List[str]]:
    """
    Load topic words for a specific language.

    Args:
        language: Language code (e.g., 'en', 'km', 'zh'). Defaults to 'en'.

    Returns:
        Dictionary with 'economic', 'policy', 'uncertainty' term lists.
    """
    topics_data = load_topics_words(language=language)
    return {
        "economic": topics_data.get("economic", ECON_LIST),
        "policy": topics_data.get("policy", POLICY_LIST),
        "uncertainty": topics_data.get("uncertainty", UNCERTAINTY_LIST),
    }


class EPU:
    """
    A class for analyzing Economic, Policy, and Uncertainty (EPU) news data.

    Attributes:
        filepath (Union[str, List[str]]): Path(s) to the news data file(s).
        cutoff_start_date (str): Inclusive baseline start date for standardization.
        cutoff_end_date (str): Inclusive baseline end date for standardization.
        non_epu_urls (list): List of urls to be removed from identified epu news.
        econ_terms (list): List of terms related to the economy.
        policy_terms (list): List of terms related to policy.
        uncertainty_terms (list): List of terms related to uncertainty.
        additional_terms (Union[List, None]): Additional terms for further categorization.
        additional_name (Union[str, None]): Name for the additional category (e.g., 'inflation', 'jobs').
        raw_files (list): List to store raw data from files.
        stds (list): List to store standard deviations for EPU scores.
        news_cols (list): List to store news count columns.
        ratio_cols (list): List to store ratio columns.
        z_score_cols (list): List to store z-score columns.

    Example:
        e = EPU(filepaths, cutoff_start_date='2020-01-01', cutoff_end_date='2020-12-31')
        e.get_epu_category(subset_condition="date >= '2015-01-01' and date < '2024-01-01'")
        e.get_count_stats()
        e.calculate_epu_score()
    """

    def __init__(
        self,
        filepath: Union[str, List[str]],
        cutoff_start_date: str | None,
        cutoff_end_date: str | None,
        non_epu_urls: list = None,
        econ_terms: list = ECON_LIST,
        policy_terms: list = POLICY_LIST,
        uncertainty_terms: list = UNCERTAINTY_LIST,
        additional_terms: Union[List, None] = None,
        additional_name: Union[str, None] = None,
        daily_tail_start: Union[str, None] = None,
        source_languages: Union[dict, None] = None,
    ):
        if isinstance(filepath, str):
            self.filepath = [filepath]
        elif isinstance(filepath, list):
            for fp in filepath:
                if not os.path.exists(fp):
                    raise FileNotFoundError(f"Cannot find {filepath}")

        self.filepath = filepath
        self.econ_terms = econ_terms
        self.policy_terms = policy_terms
        self.uncertainty_terms = uncertainty_terms
        self.additional_terms = additional_terms
        self.additional_name = additional_name
        self.raw_files = []
        self.cutoff_start_date = cutoff_start_date
        self.cutoff_end_date = cutoff_end_date
        self.daily_tail_start = daily_tail_start
        self.non_epu_urls = non_epu_urls if non_epu_urls is not None else []
        self.source_languages = source_languages or {}
        self.min_date = None
        self.max_date = None
        self.epu_stats = pd.DataFrame()
        self.stds = []
        self.params = {}
        self.news_cols = []
        self.ratio_cols = []
        self.z_score_cols = []

    @staticmethod
    def process_data(
        filepath: str,
        subset_condition: Union[str, None] = None,
        daily_tail_start: Union[str, None] = None,
    ) -> pd.DataFrame:
        """
        Reads a CSV file and processes the data.

        Args:
            filepath (str): The path to the CSV file.
            subset_condition (str): The conditions to pass on to df.query(), such as
                        "date >= 'YYYY-MM-DD'"
            daily_tail_start (str): ISO date string (YYYY-MM-DD). Articles on or after
                        this date get a daily ym (YYYY-MM-DD) instead of monthly
                        (YYYY-M). Defaults to None (all monthly).

        Returns:
            pd.DataFrame: Processed DataFrame with the "Unnamed: 0" column dropped,
                        newline characters removed from the "news" column,
                        "date" column converted to datetime, and a new "ym" column added.
        """
        # Only load columns needed downstream; gracefully handle files missing optional cols
        _all_cols = pd.read_csv(filepath, encoding="utf-8", nrows=0).columns.tolist()
        _want_cols = ["date", "body", "language", "url"]
        usecols = [c for c in _want_cols if c in _all_cols]

        # Validate required columns exist
        required_cols = ["date", "body"]
        missing_cols = [col for col in required_cols if col not in _all_cols]
        if missing_cols:
            raise ValueError(
                f"File {filepath} missing required columns: {missing_cols}. "
                f"Available columns: {_all_cols}"
            )

        df = pd.read_csv(filepath, encoding="utf-8", low_memory=False, usecols=usecols)

        df = df.drop_duplicates()
        df = df[~df["date"].isna()].reset_index(drop=True)
        if subset_condition is not None:
            df = df.query(subset_condition).reset_index(drop=True)

        df["body"] = (
            df["body"]
            .str.replace("\n", "", regex=False)
            .str.lower()
            .str.normalize("NFC")
        )
        df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df = df[~df["date"].isna()].reset_index(drop=True)

        if daily_tail_start is not None:
            tail_ts = pd.Timestamp(daily_tail_start)
            is_tail = df["date"] >= tail_ts
            df["ym"] = (
                df["date"]
                .dt.strftime("%Y-%m-%d")
                .where(
                    is_tail,
                    df["date"].dt.year.astype(str)
                    + "-"
                    + df["date"].dt.month.astype(str),
                )
            )
        else:
            df["ym"] = (
                df["date"].dt.year.astype(str) + "-" + df["date"].dt.month.astype(str)
            )
        return df

    @staticmethod
    def get_count(data: pd.DataFrame, column: str) -> pd.DataFrame:
        """
        Computes the count of occurrences for a specific column in a DataFrame
        grouped by the year-month ('ym').

        Args:
            data (pd.DataFrame): The input DataFrame.
            column (str): The column for which the count is computed.

        Returns:
            pd.DataFrame: DataFrame with the count of occurrences for the specified column

        """
        try:
            count_df = (
                data.set_index("date")
                .groupby("ym")[[str(column)]]
                .count()
                .reset_index()
                .rename({str(column): str(column) + "_count"}, axis=1)
            )
            return count_df
        except KeyError as exc:
            print(f"Column '{column}': {exc}")

    def get_epu_category(
        self,
        subset_condition=None,
        daily_tail_start=None,
        preloaded=None,
    ):
        """
        Reads the csv file that contains news and identifies the Economic/Policy/Uncertainty
        categories.

        Args:
            subset_condition (str): conditionals to pass to EPU().process_data()
            preloaded (dict | None): optional mapping of str(filepath) -> pre-loaded DataFrame
                (already filtered and processed). When provided for a file, skips disk read.
        """
        total_files = len(self.filepath)
        for file_idx, fp in enumerate(self.filepath):
            country = fp.parent.parent.name
            newspaper = fp.parent.name.replace(country, "").strip("_")
            source = f"{country}_{newspaper}"
            fp_key = str(fp)
            if preloaded is not None and fp_key in preloaded:
                raw = preloaded[fp_key].copy()
            else:
                raw = self.process_data(
                    fp,
                    subset_condition=subset_condition,
                    daily_tail_start=daily_tail_start or self.daily_tail_start,
                )

            # 6.3: Warn about NaN body rows and drop them
            n_total = len(raw)
            nan_body_mask = raw["body"].isna()
            n_nan_body = int(nan_body_mask.sum())
            if n_nan_body > 0:
                print(
                    f"  [{file_idx + 1}/{total_files}] {source}: dropping "
                    f"{n_nan_body}/{n_total} rows with missing body"
                )
                raw = raw[~nan_body_mask].reset_index(drop=True)

            # Resolve language: config-authoritative → column fallback → 'en'
            if str(fp) in self.source_languages:
                file_language = self.source_languages[str(fp)]
            elif "language" in raw.columns and not raw["language"].isna().all():
                file_language = (
                    raw["language"].mode().iloc[0]
                    if len(raw["language"].mode()) > 0
                    else "en"
                )
            else:
                file_language = "en"

            # Get terms for the detected language
            if file_language != "en":
                lang_terms = get_terms_for_language(file_language)
                econ_terms = lang_terms["economic"]
                policy_terms = lang_terms["policy"]
                uncertainty_terms = lang_terms["uncertainty"]
            else:
                # Use instance terms (which default to English)
                econ_terms = self.econ_terms
                policy_terms = self.policy_terms
                uncertainty_terms = self.uncertainty_terms

            for col, terms in zip(
                ["econ", "policy", "uncertain"],
                [econ_terms, policy_terms, uncertainty_terms],
            ):
                if terms is not None:
                    # Single-pass Aho-Corasick: boolean presence + keyword count
                    results = raw["body"].apply(
                        match_keywords, terms=terms, language=file_language
                    )
                    # Unpack tuples in one pass instead of two separate apply calls
                    unpacked = list(results)
                    raw[col] = [r[0] for r in unpacked]
                    raw[f"{col}_count"] = [r[1] for r in unpacked]
                else:
                    raw[col] = True
                    raw[f"{col}_count"] = 0

            raw["epu"] = (raw.econ) & (raw.policy) & (raw.uncertain)

            # Check for additional terms category
            if self.additional_terms:
                # For topic-specific EPU, the "additional" keyword list must match
                # the article language, just like the core E/P/U term lists.
                # The canonical topic key is stored in self.additional_name.
                additional_terms = self.additional_terms
                if self.additional_name and file_language != "en":
                    try:
                        additional_terms = get_terms_for_language(
                            file_language, additional_name=self.additional_name
                        )
                    except Exception:
                        # Fall back to the provided list (usually English).
                        additional_terms = self.additional_terms
                results = raw["body"].apply(
                    match_keywords,
                    terms=additional_terms,
                    language=file_language,
                )
                unpacked = list(results)
                raw["additional"] = [r[0] for r in unpacked]
                raw["epu"] = (raw.epu) & (raw.additional)

            if "url" in raw.columns and raw["url"].isin(self.non_epu_urls).sum() > 0:
                raw.loc[raw.url.isin(self.non_epu_urls), "epu"] = False

            # Drop columns not needed downstream to reduce raw_files memory footprint
            _keep_cols = [
                "date",
                "ym",
                "body",
                "econ",
                "policy",
                "uncertain",
                "econ_count",
                "policy_count",
                "uncertain_count",
                "epu",
                "language",
            ]
            raw = raw[[c for c in _keep_cols if c in raw.columns]]

            self.raw_files.append((source, raw, fp_key))

    def calculate_news_and_epu_counts(self, file: pd.DataFrame) -> pd.DataFrame:
        """
        The function

        """
        news_count = self.get_count(file, "body")
        epu_count = self.get_count(file[file["epu"]], "epu")
        return news_count.merge(epu_count, how="left", on="ym").fillna(0)

    def calculate_ratios(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        The function calculates the ratio of EPU news in relative to all news.
        """
        merged_df["ratio"] = merged_df["epu_count"] / merged_df["body_count"]
        return merged_df

    def calculate_extended_counts(
        self, file: pd.DataFrame, source: str
    ) -> pd.DataFrame:
        """
        Calculate counts needed for breadth, intensity, and pairwise indices.

        Returns DataFrame with per-source columns:
        - {source}_A_total: total articles
        - {source}_E_count, _P_count, _U_count: articles with >=1 keyword
        - {source}_E_kwsum, _P_kwsum, _U_kwsum: sum of keywords (for intensity)
        - {source}_EU_count, _PU_count, _EP_count: pairwise intersection counts

        Args:
            file: DataFrame with article data and boolean/count columns.
            source: Source name prefix for columns.

        Returns:
            DataFrame with extended count columns grouped by 'ym'.
        """
        # Skip empty files (0-row DataFrames lose columns on boolean indexing)
        if file.empty:
            return pd.DataFrame(columns=["ym"])

        # Create pairwise boolean columns
        file = file.copy()
        file["eu"] = file["econ"] & file["uncertain"]
        file["pu"] = file["policy"] & file["uncertain"]
        file["ep"] = file["econ"] & file["policy"]

        # Group by ym and aggregate counts
        agg_dict = {
            "body": "count",  # A_total
            "econ": "sum",  # E_count
            "policy": "sum",  # P_count
            "uncertain": "sum",  # U_count
            "eu": "sum",  # EU_count
            "pu": "sum",  # PU_count
            "ep": "sum",  # EP_count
        }

        grouped = file.groupby("ym").agg(agg_dict).reset_index()

        # Calculate keyword sums (only for articles with presence)
        # E_kwsum = sum of econ_count where econ == True
        kwsum_e = (
            file[file["econ"]]
            .groupby("ym")["econ_count"]
            .sum()
            .reset_index()
            .rename(columns={"econ_count": "E_kwsum"})
        )
        kwsum_p = (
            file[file["policy"]]
            .groupby("ym")["policy_count"]
            .sum()
            .reset_index()
            .rename(columns={"policy_count": "P_kwsum"})
        )
        kwsum_u = (
            file[file["uncertain"]]
            .groupby("ym")["uncertain_count"]
            .sum()
            .reset_index()
            .rename(columns={"uncertain_count": "U_kwsum"})
        )

        # Merge keyword sums
        grouped = grouped.merge(kwsum_e, on="ym", how="left")
        grouped = grouped.merge(kwsum_p, on="ym", how="left")
        grouped = grouped.merge(kwsum_u, on="ym", how="left")
        grouped = grouped.fillna(0)

        # Rename columns with source prefix
        rename_map = {
            "body": f"{source}_A_total",
            "econ": f"{source}_E_count",
            "policy": f"{source}_P_count",
            "uncertain": f"{source}_U_count",
            "eu": f"{source}_EU_count",
            "pu": f"{source}_PU_count",
            "ep": f"{source}_EP_count",
            "E_kwsum": f"{source}_E_kwsum",
            "P_kwsum": f"{source}_P_kwsum",
            "U_kwsum": f"{source}_U_kwsum",
        }
        grouped = grouped.rename(columns=rename_map)

        return grouped

    def merge_data_frames(
        self, epu_stats: pd.DataFrame, new_df: pd.DataFrame, source: str
    ) -> pd.DataFrame:
        """
        The function merged epu count dfs.
        """
        new_df.columns = [
            f"{source}_{col}" if col != "ym" else col for col in new_df.columns
        ]
        return (
            pd.merge(epu_stats, new_df, how="outer", on="ym")
            if not epu_stats.empty
            else new_df
        )

    def _calculate_total_news(self):
        self.news_cols = [
            col for col in self.epu_stats.columns if col.endswith("_body_count")
        ]
        self.epu_stats["news_total"] = self.epu_stats[self.news_cols].sum(axis=1)

    def _build_continuous_index(self, min_date, max_date) -> pd.DataFrame:
        """
        Build a hybrid monthly+daily continuous date index.

        If daily_tail_start is set, generates monthly dates up to the month
        before daily_tail_start, then daily dates from daily_tail_start to
        max_date. Otherwise generates a purely monthly index.

        Args:
            min_date: Start of the date range.
            max_date: End of the date range.

        Returns:
            DataFrame with a single 'date' column.
        """
        if self.daily_tail_start is not None:
            tail_ts = pd.Timestamp(self.daily_tail_start)
            # Monthly part: from min_date up to (not including) the tail month
            monthly_end = tail_ts - pd.DateOffset(months=1)
            if monthly_end >= pd.Timestamp(min_date):
                monthly_dates = pd.date_range(
                    start=min_date, end=monthly_end, freq="MS"
                )
            else:
                monthly_dates = pd.DatetimeIndex([])
            # Daily part: from tail_ts to max_date (guard against NaT when no tail articles).
            # Bounded by the tail month — the dashboard buckets daily rows by
            # day-of-month under one month key, so a run spanning two months
            # would collide Sep 1 with Aug 1.
            if pd.isna(max_date) or pd.Timestamp(max_date) < tail_ts:
                daily_dates = pd.DatetimeIndex([])
            else:
                month_end = tail_ts + pd.offsets.MonthEnd(0)
                daily_dates = pd.date_range(
                    start=tail_ts, end=min(pd.Timestamp(max_date), month_end), freq="D"
                )
            all_dates = monthly_dates.append(daily_dates)
        else:
            all_dates = pd.date_range(start=min_date, end=max_date, freq="MS")
        return pd.DataFrame({"date": all_dates})

    def get_count_stats(self, calculate_extended: bool = True):
        """
        Aggregates news and EPU counts, calculates ratios, and prepares data for
        EPU score calculation.

        Args:
            calculate_extended: If True, also calculate extended counts for
                breadth, intensity, and pairwise indices.
        """
        extended_stats = pd.DataFrame()

        for source, file, _fp_key in self.raw_files:
            counts_df = self.calculate_news_and_epu_counts(file)
            ratios_df = self.calculate_ratios(counts_df)
            self.epu_stats = self.merge_data_frames(
                self.epu_stats, ratios_df, source
            )  # .fillna(0)

            # Calculate extended counts for breadth/intensity/pairwise indices
            if calculate_extended:
                extended_df = self.calculate_extended_counts(file, source)
                if extended_stats.empty:
                    extended_stats = extended_df
                else:
                    extended_stats = pd.merge(
                        extended_stats, extended_df, how="outer", on="ym"
                    )

        # Check for date integrity
        self.epu_stats["date"] = pd.to_datetime(self.epu_stats["ym"], format="mixed")
        self.min_date, self.max_date = (
            self.epu_stats.date.min(),
            self.epu_stats.date.max(),
        )

        # Build hybrid monthly+daily continuous index
        dates_df = self._build_continuous_index(self.min_date, self.max_date)
        self.epu_stats["date"] = pd.to_datetime(self.epu_stats["date"])
        # Roll up stale daily rows from earlier incremental runs so the merge
        # below cannot drop them (ratios are recomputed from the summed counts)
        self.epu_stats = collapse_to_index_grid(
            self.epu_stats,
            self.daily_tail_start,
            ratio_cols={
                col: (
                    col[: -len("_ratio")] + "_epu_count",
                    col[: -len("_ratio")] + "_body_count",
                )
                for col in self.epu_stats.columns
                if col.endswith("_ratio")
            },
        )
        self.epu_stats = dates_df.merge(self.epu_stats, how="left", on="date").fillna(0)

        # Recompute ym from date so it always reflects the correct daily/monthly format
        if self.daily_tail_start is not None:
            tail_ts = pd.Timestamp(self.daily_tail_start)
            self.epu_stats["ym"] = self.epu_stats["date"].apply(
                lambda d: (
                    d.strftime("%Y-%m-%d")
                    if d >= tail_ts
                    else str(d.year) + "-" + str(d.month)
                )
            )
        else:
            self.epu_stats["ym"] = self.epu_stats["date"].apply(
                lambda d: str(d.year) + "-" + str(d.month)
            )

        # Merge extended stats if calculated
        if calculate_extended and not extended_stats.empty:
            extended_stats["date"] = pd.to_datetime(
                extended_stats["ym"], format="mixed"
            )
            ext_dates_df = self._build_continuous_index(self.min_date, self.max_date)
            extended_stats = collapse_to_index_grid(
                extended_stats, self.daily_tail_start
            )
            extended_stats = ext_dates_df.merge(
                extended_stats, how="left", on="date"
            ).fillna(0)
            # Merge on date, drop duplicate ym columns
            self.epu_stats = pd.merge(
                self.epu_stats,
                extended_stats.drop(columns=["ym"]),
                on="date",
                how="left",
            )

        self._calculate_total_news()
        self.ratio_cols = [
            col for col in self.epu_stats.columns if col.endswith("_ratio")
        ]
        for col in self.news_cols:
            new_col = col.replace("_body_count", "_weights")
            self.epu_stats[new_col] = self.epu_stats[col].div(
                self.epu_stats["news_total"]
            )

    def _calculate_z_score(self):
        """
        Calculates the z-scores for the EPU ratios to standardize them for
          comparison and analysis.
        """
        self.stds = []
        for ratio_col in self.ratio_cols:
            col = ratio_col.replace("_ratio", "")
            window = self.epu_stats.loc[
                baseline_mask(
                    self.epu_stats["date"],
                    self.cutoff_start_date,
                    self.cutoff_end_date,
                ),
                ratio_col,
            ]
            std = window.std()
            self.stds.append({col: std})
            # self.epu_stats[f"{col}_z_score"] = self.epu_stats[ratio_col].div(
            #     std).fillna(0).replace([np.inf, -np.inf], 0)
            if std == 0 or pd.isna(std):
                self.epu_stats[f"{col}_z_score"] = np.nan
            else:
                self.epu_stats[f"{col}_z_score"] = self.epu_stats[ratio_col] / std

        self.z_score_cols = [
            col for col in self.epu_stats.columns if col.endswith("z_score")
        ]
        self.epu_stats["z_score_unweighted"] = self.epu_stats[self.z_score_cols].mean(
            axis=1, skipna=True
        )
        self.epu_stats["z_score_weighted"] = 0
        for z_score_col in self.z_score_cols:
            weight_col = z_score_col.replace("z_score", "weights")
            self.epu_stats["z_score_weighted"] += (
                self.epu_stats[weight_col].multiply(self.epu_stats[z_score_col])
                if not pd.isna(self.epu_stats[z_score_col]).all()
                else 0
            )

    def calculate_epu_score(self):
        """
        Calculates the Economic Policy Uncertainty (EPU) scores based on z-scores and
            updates the DataFrame with these scores.
        """
        self._calculate_z_score()
        scaling_factors = {}
        for name, col in zip(
            ["weighted", "unweighted"],
            ["z_score_weighted", "z_score_unweighted"],
        ):
            mean_val = self.epu_stats.loc[
                baseline_mask(
                    self.epu_stats["date"],
                    self.cutoff_start_date,
                    self.cutoff_end_date,
                ),
                col,
            ].mean()
            if mean_val == 0 or pd.isna(mean_val):
                scaling_factor = np.nan
                scaling_factors[name] = None
            else:
                scaling_factor = 100 / mean_val
                scaling_factors[name] = float(scaling_factor)
            self.epu_stats[f"epu_{name}"] = scaling_factor * self.epu_stats[col]

        # Add additional_name column if provided
        if self.additional_name:
            self.epu_stats[f"epu_{self.additional_name}"] = self.epu_stats[
                "epu_weighted"
            ]

        # Capture params for incremental reuse
        ratio_stds = {}
        for std_dict in self.stds:
            ratio_stds.update(std_dict)
        self.params = {
            "ratio_stds": {
                k: (
                    float(v)
                    if v is not None and not (isinstance(v, float) and np.isnan(v))
                    else None
                )
                for k, v in ratio_stds.items()
            },
            "scaling_weighted": scaling_factors.get("weighted"),
            "scaling_unweighted": scaling_factors.get("unweighted"),
        }

    def calculate_all_indices(self) -> None:
        """
        Calculate all extended indices (breadth, intensity, pairwise).

        Call after get_count_stats() with calculate_extended=True.

        Adds the following columns to epu_stats:
        - E_breadth_weighted, E_breadth_unweighted
        - P_breadth_weighted, P_breadth_unweighted
        - U_breadth_weighted, U_breadth_unweighted
        - E_intensity_weighted, E_intensity_unweighted
        - P_intensity_weighted, P_intensity_unweighted
        - U_intensity_weighted, U_intensity_unweighted
        - EU_share_weighted, EU_share_unweighted
        - PU_share_weighted, PU_share_unweighted
        - EP_share_weighted, EP_share_unweighted
        """
        from .indices import IndexCalculator

        calc = IndexCalculator(self.cutoff_start_date, self.cutoff_end_date)
        sources = [col.replace("_body_count", "") for col in self.news_cols]

        # Calculate and merge each index type
        self.epu_stats = calc.calculate_breadth_indices(self.epu_stats, sources)
        self.epu_stats = calc.calculate_intensity_indices(self.epu_stats, sources)
        self.epu_stats = calc.calculate_pairwise_indices(self.epu_stats, sources)

        # Store calc so _collect_params can read stds/scaling_factors without re-running
        self._extended_calc = calc

    def _apply_stored_params(
        self,
        ratio_stds: dict,
        scaling_weighted: float | None,
        scaling_unweighted: float | None,
    ) -> None:
        """
        Apply pre-computed σ and scaling factors to self.epu_stats instead of
        recalculating them from pre-cutoff data.

        Used in incremental mode after tail rows are appended to cached pre-tail stats.
        Populates z_score columns, z_score_weighted/unweighted, epu_weighted/unweighted.
        """
        # Apply stored σ to ratio cols → z_score cols
        for ratio_col in self.ratio_cols:
            source_cat = ratio_col.replace("_ratio", "")
            std = ratio_stds.get(source_cat)
            z_col = f"{source_cat}_z_score"
            ratio_vals = self.epu_stats[ratio_col].fillna(0)
            if std is None:
                self.epu_stats[z_col] = np.nan
            elif std == 0:
                fallback_std = ratio_vals.std()
                if fallback_std == 0 or pd.isna(fallback_std):
                    self.epu_stats[z_col] = 0.0
                else:
                    self.epu_stats[z_col] = ratio_vals / fallback_std
            else:
                self.epu_stats[z_col] = ratio_vals / std

        self.z_score_cols = [
            col for col in self.epu_stats.columns if col.endswith("z_score")
        ]

        # Weighted / unweighted z-score aggregates
        self.epu_stats["z_score_unweighted"] = self.epu_stats[self.z_score_cols].mean(
            axis=1, skipna=True
        )
        self.epu_stats["z_score_weighted"] = 0
        for z_col in self.z_score_cols:
            weight_col = z_col.replace("z_score", "weights")
            if weight_col in self.epu_stats.columns:
                self.epu_stats["z_score_weighted"] += (
                    self.epu_stats[weight_col].multiply(self.epu_stats[z_col])
                    if not pd.isna(self.epu_stats[z_col]).all()
                    else 0
                )

        # Apply stored scaling factors
        sf_w = scaling_weighted if scaling_weighted is not None else np.nan
        sf_u = scaling_unweighted if scaling_unweighted is not None else np.nan
        self.epu_stats["epu_weighted"] = sf_w * self.epu_stats["z_score_weighted"]
        self.epu_stats["epu_unweighted"] = sf_u * self.epu_stats["z_score_unweighted"]

        if self.additional_name:
            self.epu_stats[f"epu_{self.additional_name}"] = self.epu_stats[
                "epu_weighted"
            ]

        # Store params for later serialisation
        self.params = {
            "ratio_stds": ratio_stds,
            "scaling_weighted": scaling_weighted,
            "scaling_unweighted": scaling_unweighted,
        }

    def calculate_group_uncertainty_counts(
        self, groups: Dict[str, List[str]]
    ) -> pd.DataFrame:
        """
        Calculate U∩G counts per source per month for each group.

        Reuses self.raw_files (populated by get_epu_category) to detect
        group keyword presence and compute intersection with uncertainty.

        Args:
            groups: Dict mapping group names to keyword lists.

        Returns:
            DataFrame with ym plus per-source columns:
            {source}_UG_{group}_count, {source}_A_total, {source}_U_count
        """
        merged = pd.DataFrame()

        for source, raw, fp_key in self.raw_files:
            # Resolve language: config-authoritative → column fallback → 'en'
            if fp_key in self.source_languages:
                file_language = self.source_languages[fp_key]
            elif "language" in raw.columns and not raw["language"].isna().all():
                file_language = (
                    raw["language"].mode().iloc[0]
                    if len(raw["language"].mode()) > 0
                    else "en"
                )
            else:
                file_language = "en"

            # Accumulate new group columns in a dict; concat once to avoid fragmentation
            new_cols: dict = {}
            agg_dict = {}

            for group_name, terms in groups.items():
                ug_col = f"UG_{group_name}"
                presence = raw["body"].apply(
                    lambda text, t=terms, lang=file_language: match_keywords(
                        text, t, lang
                    )[0]
                )
                new_cols[ug_col] = raw["uncertain"] & presence
                agg_dict[ug_col] = "sum"

            agg_dict["body"] = "count"
            agg_dict["uncertain"] = "sum"

            df = pd.concat(
                [
                    raw[["ym", "body", "uncertain"]],
                    pd.DataFrame(new_cols, index=raw.index),
                ],
                axis=1,
            )
            grouped = df.groupby("ym").agg(agg_dict).reset_index()

            rename_map = {
                "body": f"{source}_A_total",
                "uncertain": f"{source}_U_count",
            }
            for group_name in groups:
                rename_map[f"UG_{group_name}"] = f"{source}_UG_{group_name}_count"

            grouped = grouped.rename(columns=rename_map)

            if merged.empty:
                merged = grouped
            else:
                merged = pd.merge(merged, grouped, how="outer", on="ym")

        return merged
