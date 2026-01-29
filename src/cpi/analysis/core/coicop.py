"""COICOP hierarchy utilities."""

import pandas as pd


def parse_coicop_level(code: str, level: int) -> str:
    """
    Extract COICOP code at specified level.

    Parameters
    ----------
    code : str
        Full COICOP code (e.g., "01.1.8.9")
    level : int
        Hierarchy level (1, 2, 3, or 4)

    Returns
    -------
    str
        COICOP code at specified level
        - Level 1: "01"
        - Level 2: "01.1"
        - Level 3: "01.1.8"
        - Level 4: "01.1.8.9"

    Examples
    --------
    >>> parse_coicop_level("01.1.8.9", 1)
    "01"
    >>> parse_coicop_level("01.1.8.9", 2)
    "01.1"
    >>> parse_coicop_level("01.1.8.9", 3)
    "01.1.8"
    >>> parse_coicop_level("01.1.8.9", 4)
    "01.1.8.9"
    """
    if pd.isna(code) or not isinstance(code, str):
        return None

    parts = code.split(".")

    if level == 1:
        return parts[0] if len(parts) >= 1 else None
    elif level == 2:
        return ".".join(parts[:2]) if len(parts) >= 2 else None
    elif level == 3:
        return ".".join(parts[:3]) if len(parts) >= 3 else None
    elif level == 4:
        return code
    else:
        raise ValueError(f"Invalid level: {level}. Must be 1, 2, 3, or 4.")


def add_coicop_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add COICOP level columns to DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'coicop_code' column

    Returns
    -------
    pd.DataFrame
        DataFrame with added columns:
        - coicop_1: Level 1 code
        - coicop_2: Level 2 code
        - coicop_3: Level 3 code
        - coicop_4: Level 4 code (same as coicop_code)
    """
    df = df.copy()

    df["coicop_1"] = df["coicop_code"].apply(lambda x: parse_coicop_level(x, 1))
    df["coicop_2"] = df["coicop_code"].apply(lambda x: parse_coicop_level(x, 2))
    df["coicop_3"] = df["coicop_code"].apply(lambda x: parse_coicop_level(x, 3))
    df["coicop_4"] = df["coicop_code"].apply(lambda x: parse_coicop_level(x, 4))

    return df
