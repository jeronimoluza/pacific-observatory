"""Gemini classification stage for the COICOP pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .classification import run_coicop_matching
from .utils import get_project_root


def run_classify(project_root: Path) -> None:
    data_dir = project_root / "data" / "cpi" / "coicopping"
    cache_path = data_dir / "prepared_cache.parquet"

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Prepared cache not found at {cache_path}. Run load stage first."
        )

    df_prepared = pd.read_parquet(cache_path)
    run_coicop_matching(df_prepared=df_prepared, project_root=project_root)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini classification stage for COICOP pipeline"
    )
    parser.parse_args()

    project_root = get_project_root()
    try:
        run_classify(project_root)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
