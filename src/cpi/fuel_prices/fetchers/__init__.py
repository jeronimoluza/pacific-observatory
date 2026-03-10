"""Fetcher registry mapping source_key → (fetch_fn, fallback_date, full_refresh)."""

from datetime import date

from .australia import fetch_accc, fetch_au_aip_tgp
from .cambodia import fetch_kh_ptt
from .china import fetch_cn_ndrc_max_retail_prices
from .fiji import fetch_fj_fccc_orders
from .indonesia import fetch_id_oto
from .japan import fetch_jp_anre_excel
from .korea import fetch_kr_opinet_weekly
from .lao import fetch_lao, fetch_lao_kpl
from .malaysia import fetch_malaysia_mof
from .mongolia import fetch_mn_nso_weekly_aimag, fetch_mongolia_data_mn
from .myanmar import fetch_myanmar_gnlm
from .new_zealand import fetch_nz_mbie_weekly
from .singapore import (
    fetch_sg_singstat_avg_retail_prices,
    fetch_sg_spc_latest_pump_prices,
)
from .tonga import fetch_to_mted_petroleum_prices
from .pacific_islands import (
    fetch_png_iccc,
    fetch_samoa_mof,
    fetch_solomon_islands,
    fetch_vanuatu_doe,
)
from .philippines import fetch_ph_doe_visayas, fetch_philippines_doe
from .thailand import fetch_th_eppo_p04, fetch_thailand_eppo_ngv
from .timor_leste import fetch_timor_anp
from .global_commodities import (
    fetch_imf_fred_prices,
    fetch_investing_commodities,
    fetch_eia_spot_prices,
    fetch_wb_pink_sheet,
)
from .vietnam import fetch_vn_petrolimex

# Registry: source_key → (fetch_fn, fallback_date, full_refresh)
# full_refresh=True means existing rows for this source are dropped before writing
FETCHER_REGISTRY: dict[str, tuple] = {
    # Australia
    "au_aip_tgp_weekly": (fetch_au_aip_tgp, date(2015, 1, 1), True),
    "au_accc_5largestcities_quarterly": (fetch_accc, date(2019, 1, 1), False),
    # Cambodia
    "kh_ptt_monthly_prices": (fetch_kh_ptt, date(2020, 1, 1), False),
    # "kh_moc_fuel_notices":             (fetch_cambodia_moc,          date(2024, 1, 1),  False),
    # Fiji
    "fj_fccc_order_prices": (fetch_fj_fccc_orders, date(2020, 1, 1), False),
    # Indonesia
    "id_oto_monthly_prices": (fetch_id_oto, date(2015, 1, 1), True),
    # Japan
    "jp_anre_weekly_petroleum_2026": (fetch_jp_anre_excel, date(2020, 1, 1), False),
    # Korea
    "kr_opinet_history_weekly": (fetch_kr_opinet_weekly, date(2014, 1, 1), False),
    # Lao
    "lao_state_fuel_oil_prices": (fetch_lao, date(2023, 1, 1), False),
    "lao_kpl_fuel_notices": (fetch_lao_kpl, date(2025, 12, 1), False),
    # Malaysia
    "my_mof_weekly_petroleum": (fetch_malaysia_mof, date(2023, 1, 1), False),
    # Mongolia NSO
    "mn_nso_aimag_weekly_fuel": (fetch_mn_nso_weekly_aimag, date(2023, 12, 31), False),
    # Mongolia data.mn (three datasets share one fetcher)
    "mn_data_mn_a92_aimags": (fetch_mongolia_data_mn, date(2023, 1, 1), False),
    "mn_data_mn_diesel_aimags": (fetch_mongolia_data_mn, date(2023, 1, 1), False),
    "mn_data_mn_fuel_ulaanbaatar": (fetch_mongolia_data_mn, date(2023, 1, 1), False),
    # Myanmar
    "mm_gnlm_fuel_reference_prices": (fetch_myanmar_gnlm, date(2024, 1, 1), False),
    # New Zealand
    "nz_mbie_weekly_fuel": (fetch_nz_mbie_weekly, date(2020, 1, 1), True),
    # Singapore
    "sg_singstat_avg_retail_prices_monthly": (
        fetch_sg_singstat_avg_retail_prices,
        date(2015, 1, 1),
        False,
    ),
    "sg_spc_pump_prices_daily": (
        fetch_sg_spc_latest_pump_prices,
        date(2024, 1, 1),
        False,
    ),
    # Tonga
    "to_mted_petroleum_prices_monthly": (
        fetch_to_mted_petroleum_prices,
        date(2020, 1, 1),
        False,
    ),
    # Pacific Islands
    "pg_iccc_monthly_irp": (fetch_png_iccc, date(2023, 1, 1), False),
    "ws_mof_monthly_fuel_prices": (fetch_samoa_mof, date(2023, 1, 1), False),
    "vu_doe_retail_petrol_diesel_2025": (fetch_vanuatu_doe, date(2023, 1, 1), False),
    "sb_price_control_petroleum_2025": (fetch_solomon_islands, date(2023, 1, 1), False),
    "sb_price_control_lpg_2025": (fetch_solomon_islands, date(2023, 1, 1), False),
    # Philippines
    "ph_doe_retail_pump_prices": (fetch_philippines_doe, date(2024, 1, 1), False),
    "ph_doe_visayas_weekly": (fetch_ph_doe_visayas, date(2020, 1, 1), False),
    # Thailand
    "th_eppo_p04_monthly": (fetch_th_eppo_p04, date(2020, 1, 1), True),
    "th_eppo_ngv_bangkok_2025": (fetch_thailand_eppo_ngv, date(2023, 1, 1), False),
    # Timor-Leste
    "tl_anp_daily_fuel_price": (fetch_timor_anp, date(2024, 1, 1), False),
    # China
    "cn_ndrc_max_retail_prices_biweekly": (
        fetch_cn_ndrc_max_retail_prices,
        date(2024, 1, 1),
        False,
    ),
    # Vietnam
    "vn_petrolimex_retail": (fetch_vn_petrolimex, date(2019, 12, 31), False),
    # Global & EAP commodity benchmarks → commodity_prices.csv
    "global_investing_daily": (fetch_investing_commodities, date(2015, 1, 1), False),
    "global_eia_spot_daily": (fetch_eia_spot_prices, date(2015, 1, 1), False),
    "global_wb_pinksheet": (fetch_wb_pink_sheet, date(2000, 1, 1), False),
    "global_imf_fred_monthly": (fetch_imf_fred_prices, date(2000, 1, 1), False),
}

__all__ = ["FETCHER_REGISTRY"]
