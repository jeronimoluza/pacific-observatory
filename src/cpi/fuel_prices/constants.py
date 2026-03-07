"""Shared constants for the fuel_prices module."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data" / "cpi" / "fuel_prices"
PRIMARY_CSV = DATA_DIR / "eap_fuel_prices.csv"
SECONDARY_CSV = DATA_DIR / "eap_fuel_prices_secondary.csv"
COMMODITY_CSV = DATA_DIR / "commodity_prices.csv"
FETCH_STATE_JSON = DATA_DIR / ".fetch_state.json"
JAPAN_DIR = DATA_DIR / "japan_prices"

PALETTE = [
    "#1d77b2",
    "#d95e10",
    "#00a37c",
    "#e7298a",
    "#66a61e",
    "#e6ab02",
    "#7570b3",
    "#a6761d",
    "#666666",
    "#1b9e77",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#bcbd22",
    "#ff7f0e",
    "#2ca02c",
    "#e377c2",
    "#7f7f7f",
    "#aec7e8",
]

COLUMNS = [
    "country",
    "wb_iso3",
    "subnational_area",
    "city",
    "fuel_family",
    "fuel_product",
    "quality_group",
    "octane_ron",
    "ethanol_pct",
    "sulfur_standard",
    "gas_type",
    "delivery_type",
    "consumer_segment",
    "price_local",
    "currency",
    "unit",
    "tax_status",
    "source_key",
    "source_name",
    "source_url",
    "source_type",
    "scrape_ts",
    "effective_from",
    "effective_to",
    "observation_date",
    "publication_frequency",
    "observation_method",
    "status",
    "notes",
    "observation_hash",
]

# Countries whose data is fully replaced by the secondary source in the visualizer.
# Primary-CSV rows for these are dropped when the secondary CSV exists.
SECONDARY_ONLY_COUNTRIES = {
    "Australia",
    "Fiji",
    "Indonesia",
    "Japan",
    "Korea, Rep.",
    "Mongolia",
    "New Zealand",
    "Philippines",
    "Thailand",
    "Vietnam",
    "Viet Nam",
}
