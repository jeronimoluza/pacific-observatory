"""Generate an Excel source inventory for observed fuel source keys.

Run directly::

    python -m src.cpi.fuel_prices.gen_sources_excel

Output: data/cpi/fuel_prices/fuel_source_inventory.xlsx
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .constants import DATA_DIR
from .source_inventory import (
    DEFAULT_ENRICHED_CSV,
    SOURCE_INVENTORY_COLUMNS,
    build_source_inventory_rows,
)

DEFAULT_OUTPUT_PATH = DATA_DIR / "fuel_source_inventory.xlsx"


def gen_sources_excel(
    out_path: Path | None = None,
    enriched_csv_path: Path | None = None,
) -> Path:
    """Write the observed fuel source inventory workbook."""
    output_path = out_path or DEFAULT_OUTPUT_PATH
    rows = build_source_inventory_rows(enriched_csv_path or DEFAULT_ENRICHED_CSV)
    frame = pd.DataFrame(rows, columns=SOURCE_INVENTORY_COLUMNS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="sources", index=False)

    print(f"  [sources] Written Excel inventory: {output_path}")
    return output_path


if __name__ == "__main__":
    gen_sources_excel()
