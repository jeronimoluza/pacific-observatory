"""Storage helpers for per-source fuel price data.

We store each (country, source_key) as its own CSV under:
  data/cpi/fuel_prices/<country_slug>/<source_key>/observations.csv

This avoids appending everything into a single eap_fuel_prices*.csv file and
makes source-level backfills and audits much simpler.
"""

from __future__ import annotations

import re
from pathlib import Path

from .constants import DATA_DIR


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def country_slug(country: str) -> str:
    """Stable ASCII slug for directory naming."""
    s = (country or "").strip().lower()
    s = s.replace("&", "and")
    s = _NON_ALNUM_RE.sub("_", s)
    s = s.strip("_")
    return s or "unknown"


def source_dir(country: str, source_key: str, *, base_dir: Path = DATA_DIR) -> Path:
    return base_dir / country_slug(country) / str(source_key).strip()


def source_csv_path(
    country: str, source_key: str, *, base_dir: Path = DATA_DIR
) -> Path:
    return source_dir(country, source_key, base_dir=base_dir) / "observations.csv"
