"""Rows of a source's news.csv that the annotator counts (deduped, dated, in subset, with body)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def clean_chunks(
    news_csv: Path,
    subset_start: pd.Timestamp | None = None,
    subset_end: pd.Timestamp | None = None,
    chunksize: int = 20_000,
):
    """Yield ``(rows, n_deduped, n_nan_date, n_nan_body)`` per chunk of news.csv.

    ``rows`` are the rows `annotate_source` annotates: deduped, dated, inside the
    subset, with a body. The cache gate counts them per month with the same filter.
    """
    cols = pd.read_csv(news_csv, encoding="utf-8", nrows=0).columns.tolist()
    want = [c for c in ("date", "body", "language", "url") if c in cols]

    seen: set[int] = set()
    reader = pd.read_csv(news_csv, encoding="utf-8", usecols=want, chunksize=chunksize)
    for chunk in reader:
        # One row per url, the first one in the file (the earliest written),
        # BEFORE date parsing. Rows without a url fall back to the row content.
        # The seen set keeps that global across chunks.
        hashes = pd.util.hash_pandas_object(chunk, index=False).to_numpy()
        if "url" in chunk.columns:
            has_url = chunk["url"].notna().to_numpy()
            url_hashes = pd.util.hash_pandas_object(
                chunk["url"], index=False
            ).to_numpy()
            hashes = np.where(has_url, url_hashes, hashes)
        keep = []
        for i, h in enumerate(hashes):
            if h not in seen:
                seen.add(h)
                keep.append(i)
        chunk = chunk.iloc[keep].reset_index(drop=True)

        n_deduped = len(chunk)
        chunk["date"] = pd.to_datetime(
            chunk.get("date"), format="mixed", errors="coerce"
        )
        n_nan_date = int(chunk["date"].isna().sum())
        chunk = chunk[~chunk["date"].isna()].reset_index(drop=True)

        if subset_start is not None:
            chunk = chunk[chunk["date"] >= subset_start]
        if subset_end is not None:
            chunk = chunk[chunk["date"] <= subset_end]
        chunk = chunk.reset_index(drop=True)

        n_nan_body = 0
        if "body" in chunk.columns:
            n_nan_body = int(chunk["body"].isna().sum())
            chunk = chunk[~chunk["body"].isna()].reset_index(drop=True)

        yield chunk, n_deduped, n_nan_date, n_nan_body
