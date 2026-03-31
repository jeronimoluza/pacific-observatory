"""Per-source storage helpers: paths, slugs, CSV I/O."""

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def country_slug(name: str) -> str:
    """Normalize a country name to a filesystem-safe slug.

    'New Zealand' → 'new_zealand', 'Timor-Leste' → 'timor_leste'
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def source_data_path(
    pipeline: str,
    country: str,
    source_key: str,
    filename: str = "observations.csv",
    base_dir: Path = Path("data"),
) -> Path:
    """Canonical path for a source's data file.

    Returns: data/{pipeline}/{country_slug}/{source_key}/{filename}
    """
    return base_dir / pipeline / country_slug(country) / source_key / filename


def load_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Load a CSV, returning an empty schema-aligned frame if missing."""
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    if columns:
        return pd.DataFrame(columns=pd.Index(columns))
    return pd.DataFrame()


def save_csv(
    df: pd.DataFrame,
    path: Path,
    columns: list[str] | None = None,
) -> None:
    """Persist a CSV. If columns provided, reorder and fill missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df = df[columns]
    df.to_csv(path, index=False)
    logger.info("Saved %d rows → %s", len(df), path)
