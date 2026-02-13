"""Summary statistics for the all_countries_supermarket_prices dataset."""

from pathlib import Path

import pandas as pd

from coicop_utils import load_all_coicop_levels


def main():
    project_root = Path(__file__).resolve().parents[3]
    filepath = (
        project_root
        / "data"
        / "cpi"
        / "analysis"
        / "all_countries_supermarket_prices.csv"
    )

    df = pd.read_csv(filepath, usecols=["url_hash", "coicop_code", "source", "country"])

    # --- Number of countries ---
    n_countries = df["country"].nunique()
    print(f"Number of countries: {n_countries}")

    # --- Number of sources ---
    n_sources = df["source"].nunique()
    print(f"Number of sources: {n_sources}")

    # --- Load full COICOP hierarchy (code -> title) for all levels ---
    coicop_mappings = load_all_coicop_levels()

    # --- Split classified vs unclassified ---
    df_classified = df[df["coicop_code"].notna()].copy()
    df_unclassified = df[df["coicop_code"].isna()]
    n_unclassified = df_unclassified["url_hash"].nunique()

    df_classified["coicop_code"] = df_classified["coicop_code"].astype(str)

    # --- Unique products per COICOP category at each digit level ---
    level_dataframes = {}

    for level in range(1, 5):
        df_classified[f"level_{level}"] = df_classified["coicop_code"].apply(
            lambda code, lv=level: ".".join(code.split(".")[:lv])
        )

        counts = df_classified.groupby(f"level_{level}")["url_hash"].nunique()

        # Build full list from COICOP hierarchy, filling missing with 0
        mapping = coicop_mappings[level]
        all_codes = sorted(mapping.keys())

        rows = []
        print(f"\n{'=' * 60}")
        print(f"COICOP Level {level} — unique products (url_hash) per category")
        print(f"{'=' * 60}")
        total = 0
        for code in all_codes:
            title = mapping[code]
            n = counts.get(code, 0)
            total += n
            rows.append(
                {"COICOP Code": code, "COICOP Title": title, "Unique Products": n}
            )
            print(f"  {code} {title}: {n:,}")
        rows.append(
            {
                "COICOP Code": "",
                "COICOP Title": "Unclassified Products",
                "Unique Products": n_unclassified,
            }
        )
        rows.append(
            {
                "COICOP Code": "",
                "COICOP Title": "TOTAL",
                "Unique Products": total + n_unclassified,
            }
        )
        print(f"  Unclassified Products: {n_unclassified:,}")
        print(f"  TOTAL: {total + n_unclassified:,}")

        level_dataframes[level] = pd.DataFrame(rows)

    # --- Export to Excel with one sheet per level ---
    xlsx_path = project_root / "data" / "cpi" / "analysis" / "data_summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for level, level_df in level_dataframes.items():
            level_df.to_excel(writer, sheet_name=f"COICOP Level {level}", index=False)
    print(f"\nExported to {xlsx_path}")


if __name__ == "__main__":
    main()
