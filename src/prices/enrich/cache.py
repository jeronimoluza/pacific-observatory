import pandas as pd


def read_cache() -> pd.DataFrame:
    raise NotImplementedError  # Task 2.3


def append_enrichments(rows: list[dict]) -> None:
    raise NotImplementedError  # Task 2.3


def append_failures(rows: list[dict]) -> None:
    raise NotImplementedError  # Task 4.1


def existing_keys() -> set[str]:
    raise NotImplementedError  # Task 2.3


def enforce_collision_invariant() -> int:
    """Prune rows from _failed.parquet whose cache_key also exists in enrichments.parquet.

    Returns number of pruned rows.
    """
    raise NotImplementedError  # Task 4.2
