"""Fetcher registry mapping source_key → FetcherConfig."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Literal

import pandas as pd

from .australia import (
    fetch_accc,
    fetch_au_aip_tgp,
    fetch_au_fuelwatch_historic_csv,
    fetch_au_fuelwatch_perth,
    fetch_au_nsw_fuelcheck_history,
)
from .cambodia import fetch_cambodia_moc, fetch_kh_ptt
from .china import fetch_cn_ndrc_max_retail_prices
from .fiji import fetch_fj_fccc_orders
from .hong_kong import (
    fetch_hk_consumer_council_diesel,
    fetch_hk_consumer_council_petrol,
)
from .indonesia import fetch_id_oto, fetch_id_pertamina_pengumuman
from .japan import fetch_jp_anre_excel
from .korea import fetch_kr_opinet_daily, fetch_kr_opinet_weekly
from .lao import fetch_lao, fetch_lao_kpl
from .malaysia import fetch_malaysia_datagovmy, fetch_malaysia_mof
from .mongolia import fetch_mn_nso_weekly_aimag, fetch_mongolia_data_mn
from .myanmar import fetch_myanmar_denko, fetch_myanmar_gnlm
from .new_zealand import fetch_nz_gaspy_stats_daily, fetch_nz_mbie_weekly
from .singapore import (
    fetch_sg_singstat_avg_retail_prices,
    fetch_sg_spc_latest_pump_prices,
    fetch_sg_caltex_pump_prices,
)
from .taiwan import fetch_tw_cpc_history_prices, fetch_tw_moea_nationwide_avg
from .tonga import fetch_to_mted_petroleum_prices
from .pacific_islands import (
    fetch_png_iccc,
    fetch_samoa_mof,
    fetch_solomon_islands,
    fetch_vanuatu_doe,
)
from .philippines import fetch_ph_doe_visayas, fetch_philippines_doe
from .thailand import (
    fetch_th_bangchak_retail_history,
    fetch_th_eppo_p04,
    fetch_th_eppo_retail_daily,
    fetch_th_or_pttor_current_oil_price,
    fetch_thailand_eppo_ngv,
)
from .timor_leste import fetch_timor_anp
from .global_commodities import fetch_investing_commodities
from .vietnam import fetch_vn_petrolimex

# ── Cadence type ──────────────────────────────────────────────────────────────

Cadence = Literal["daily", "weekly", "monthly", "quarterly", "irregular", "manual"]

# ── FetcherConfig dataclass ───────────────────────────────────────────────────


@dataclass(frozen=True)
class FetcherConfig:
    """Registry entry for a single fuel price source."""

    fn: Callable[[date], pd.DataFrame]
    fallback_date: date
    source_name: str
    country: str
    homepage: str
    cadence: Cadence
    full_refresh: bool = False


# ── Registry ──────────────────────────────────────────────────────────────────

FETCHER_REGISTRY: dict[str, FetcherConfig] = {
    # ── Australia ─────────────────────────────────────────────────────────────
    "au_aip_tgp_weekly": FetcherConfig(
        fn=fetch_au_aip_tgp,
        fallback_date=date(2015, 1, 1),
        source_name="Australian Institute of Petroleum Terminal Gate Prices",
        country="Australia",
        homepage="https://www.aip.com.au/aip-tgp-data",
        cadence="weekly",
        full_refresh=True,
    ),
    "au_accc_5largestcities_quarterly": FetcherConfig(
        fn=fetch_accc,
        fallback_date=date(2019, 1, 1),
        source_name="ACCC Petrol Monitoring — 5 Largest Cities Quarterly Average",
        country="Australia",
        homepage="https://www.accc.gov.au/by-industry/petrol-and-fuel",
        cadence="quarterly",
    ),
    "au_fuelwatch_perth_daily": FetcherConfig(
        fn=fetch_au_fuelwatch_perth,
        fallback_date=date(2024, 1, 1),
        source_name="FuelWatch WA (Perth) Daily Prices",
        country="Australia",
        homepage="https://www.fuelwatch.wa.gov.au",
        cadence="daily",
    ),
    "au_nsw_fuelcheck_history": FetcherConfig(
        fn=fetch_au_nsw_fuelcheck_history,
        fallback_date=date(2016, 8, 1),
        source_name="NSW FuelCheck Price History",
        country="Australia",
        homepage="https://data.nsw.gov.au/data/dataset/fuel-check",
        cadence="irregular",
    ),
    "au_fuelwatch_perth_daily_historic": FetcherConfig(
        fn=fetch_au_fuelwatch_historic_csv,
        fallback_date=date(2026, 1, 1),
        source_name="FuelWatch WA (Perth) Historic CSV",
        country="Australia",
        homepage="https://www.fuelwatch.wa.gov.au/retail/historic",
        cadence="manual",
    ),
    # ── Cambodia ──────────────────────────────────────────────────────────────
    "kh_ptt_monthly_prices": FetcherConfig(
        fn=fetch_kh_ptt,
        fallback_date=date(2020, 1, 1),
        source_name="PTT Cambodia Monthly Fuel Prices",
        country="Cambodia",
        homepage="https://www.ptt.com.kh/products-and-services-oil-price",
        cadence="monthly",
    ),
    "kh_moc_fuel_notices": FetcherConfig(
        fn=fetch_cambodia_moc,
        fallback_date=date(2024, 1, 1),
        source_name="Cambodia Ministry of Commerce Fuel Price Notices",
        country="Cambodia",
        homepage="https://moc.gov.kh/en-US/news/",
        cadence="manual",  # GraphQL endpoint requires Bearer token (403 without auth)
    ),
    # ── Fiji ──────────────────────────────────────────────────────────────────
    "fj_fccc_order_prices": FetcherConfig(
        fn=fetch_fj_fccc_orders,
        fallback_date=date(2020, 1, 1),
        source_name="Fiji Commerce Commission (FCCC) Petroleum Price Control Orders",
        country="Fiji",
        homepage="https://fccc.gov.fj/petroleum/",
        cadence="irregular",
    ),
    # ── Hong Kong ─────────────────────────────────────────────────────────────
    "hk_consumer_council_petrol_daily": FetcherConfig(
        fn=fetch_hk_consumer_council_petrol,
        fallback_date=date(2020, 1, 1),
        source_name="Hong Kong Consumer Council — Petrol Prices",
        country="Hong Kong SAR, China",
        homepage="https://oil-price.consumer.org.hk/en/",
        cadence="daily",
    ),
    "hk_consumer_council_diesel_daily": FetcherConfig(
        fn=fetch_hk_consumer_council_diesel,
        fallback_date=date(2020, 1, 1),
        source_name="Hong Kong Consumer Council — Diesel Prices",
        country="Hong Kong SAR, China",
        homepage="https://oil-price.consumer.org.hk/en/diesel/",
        cadence="daily",
    ),
    # ── Indonesia ─────────────────────────────────────────────────────────────
    "id_oto_monthly_prices": FetcherConfig(
        fn=fetch_id_oto,
        fallback_date=date(2015, 1, 1),
        source_name="OTO.com Indonesia Monthly Fuel Prices",
        country="Indonesia",
        homepage="https://www.oto.com/en/harga-bbm",
        cadence="monthly",
        full_refresh=True,
    ),
    "id_pertamina_pengumuman_non_subsidi": FetcherConfig(
        fn=fetch_id_pertamina_pengumuman,
        fallback_date=date(2023, 7, 31),
        source_name="Pertamina Pengumuman Harga BBM Non-Subsidi",
        country="Indonesia",
        homepage="https://www.pertamina.com/pengumuman",
        cadence="irregular",
    ),
    # ── Japan ─────────────────────────────────────────────────────────────────
    "jp_anre_weekly_petroleum_2026": FetcherConfig(
        fn=fetch_jp_anre_excel,
        fallback_date=date(2020, 1, 1),
        source_name="ANRE (Agency for Natural Resources and Energy) Weekly Petroleum Survey",
        country="Japan",
        homepage="https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
        cadence="weekly",
    ),
    # ── Korea ─────────────────────────────────────────────────────────────────
    "kr_opinet_history_weekly": FetcherConfig(
        fn=fetch_kr_opinet_weekly,
        fallback_date=date(2014, 1, 1),
        source_name="Korea Opinet Oil Price History (Weekly National Average)",
        country="Korea, Rep.",
        homepage="https://www.opinet.co.kr/user/doop/doopOilHistory.do",
        cadence="weekly",
    ),
    "kr_opinet_daily_avg": FetcherConfig(
        fn=fetch_kr_opinet_daily,
        fallback_date=date(2024, 1, 1),
        source_name="Korea Opinet Daily Average Prices",
        country="Korea, Rep.",
        homepage="https://www.opinet.co.kr/user/main/mainView.do",
        cadence="daily",
    ),
    # ── Lao PDR ───────────────────────────────────────────────────────────────
    "lao_state_fuel_oil_prices": FetcherConfig(
        fn=fetch_lao,
        fallback_date=date(2023, 1, 1),
        source_name="Lao State Fuel Company — Provincial Retail Prices",
        country="Lao PDR",
        homepage="https://www.laostatefuel.com/en/gas-price.html",
        cadence="irregular",
    ),
    "lao_kpl_fuel_notices": FetcherConfig(
        fn=fetch_lao_kpl,
        fallback_date=date(2025, 12, 1),
        source_name="KPL — MoIC Fuel Price Notices",
        country="Lao PDR",
        homepage="https://kpl.gov.la/En/News.aspx?cat=13",
        cadence="irregular",
    ),
    # ── Malaysia ──────────────────────────────────────────────────────────────
    "my_mof_weekly_petroleum": FetcherConfig(
        fn=fetch_malaysia_mof,
        fallback_date=date(2023, 1, 1),
        source_name="Malaysia Ministry of Finance — Weekly Petroleum Retail Prices",
        country="Malaysia",
        homepage="https://www.mof.gov.my/portal/en/news/press-release/retail-price",
        cadence="weekly",
    ),
    "my_datagovmy_weekly_fuelprice": FetcherConfig(
        fn=fetch_malaysia_datagovmy,
        fallback_date=date(2017, 3, 1),
        source_name="data.gov.my — Weekly Fuel Prices",
        country="Malaysia",
        homepage="https://data.gov.my/data-catalogue/fuelprice",
        cadence="weekly",
    ),
    # ── Mongolia ──────────────────────────────────────────────────────────────
    "mn_nso_aimag_weekly_fuel": FetcherConfig(
        fn=fetch_mn_nso_weekly_aimag,
        fallback_date=date(2023, 12, 31),
        source_name="NSC Mongolia Weekly Fuel Prices — 1212.mn (Aimag)",
        country="Mongolia",
        homepage="https://data.1212.mn",
        cadence="weekly",
    ),
    "mn_data_mn_a92_aimags": FetcherConfig(
        fn=fetch_mongolia_data_mn,
        fallback_date=date(2023, 1, 1),
        source_name="data.mn Mongolia Weekly Gasoline A-92 Prices by Aimag",
        country="Mongolia",
        homepage="https://data.mn/en/data/weekly-gasoline-prices-aimags",
        cadence="weekly",
    ),
    "mn_data_mn_diesel_aimags": FetcherConfig(
        fn=fetch_mongolia_data_mn,
        fallback_date=date(2023, 1, 1),
        source_name="data.mn Mongolia Weekly Diesel Prices by Aimag",
        country="Mongolia",
        homepage="https://data.mn/en/data/weekly-diesel-prices-aimags",
        cadence="weekly",
    ),
    "mn_data_mn_fuel_ulaanbaatar": FetcherConfig(
        fn=fetch_mongolia_data_mn,
        fallback_date=date(2023, 1, 1),
        source_name="data.mn Mongolia Weekly Fuel Prices in Ulaanbaatar",
        country="Mongolia",
        homepage="https://data.mn/en/data/weekly-fuel-prices-ulaanbaatar",
        cadence="weekly",
    ),
    # ── Myanmar ───────────────────────────────────────────────────────────────
    "mm_gnlm_fuel_reference_prices": FetcherConfig(
        fn=fetch_myanmar_gnlm,
        fallback_date=date(2024, 1, 1),
        source_name="Myanmar Global New Light — Fuel Reference Prices",
        country="Myanmar",
        homepage="https://www.gnlm.com.mm/",
        cadence="irregular",
    ),
    "mm_denko_station_daily": FetcherConfig(
        fn=fetch_myanmar_denko,
        fallback_date=date(2025, 1, 1),
        source_name="Denko Myanmar — All Station Daily Fuel Rates",
        country="Myanmar",
        homepage="https://denkomyanmar.com/all-denko-station-daily-fuel-rates/",
        cadence="daily",
        full_refresh=True,
    ),
    # ── New Zealand ───────────────────────────────────────────────────────────
    "nz_mbie_weekly_fuel": FetcherConfig(
        fn=fetch_nz_mbie_weekly,
        fallback_date=date(2020, 1, 1),
        source_name="MBIE Weekly Fuel Price Monitoring",
        country="New Zealand",
        homepage="https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring/",
        cadence="weekly",
        full_refresh=True,
    ),
    "nz_gaspy_stats_daily": FetcherConfig(
        fn=fetch_nz_gaspy_stats_daily,
        fallback_date=date(2024, 1, 1),
        source_name="Gaspy NZ Average Fuel Prices",
        country="New Zealand",
        homepage="https://www.gaspy.nz/stats.html",
        cadence="daily",
    ),
    # ── Singapore ─────────────────────────────────────────────────────────────
    "sg_singstat_avg_retail_prices_monthly": FetcherConfig(
        fn=fetch_sg_singstat_avg_retail_prices,
        fallback_date=date(2015, 1, 1),
        source_name="Singapore Department of Statistics — Retail Fuel Prices",
        country="Singapore",
        homepage="https://tablebuilder.singstat.gov.sg/table/TS/M213761",
        cadence="monthly",
    ),
    "sg_spc_pump_prices_daily": FetcherConfig(
        fn=fetch_sg_spc_latest_pump_prices,
        fallback_date=date(2024, 1, 1),
        source_name="SPC Latest Pump Prices",
        country="Singapore",
        homepage="https://www.spc.com.sg/our-business/spc-service-station/latest-pump-price/",
        cadence="daily",
    ),
    "sg_caltex_pump_prices_daily": FetcherConfig(
        fn=fetch_sg_caltex_pump_prices,
        fallback_date=date(2024, 1, 1),
        source_name="Caltex Singapore Fuel Prices",
        country="Singapore",
        homepage="https://www.caltex.com/sg/motorists/fuel-prices.html",
        cadence="daily",
    ),
    # ── Taiwan ────────────────────────────────────────────────────────────────
    "tw_moea_nationwide_avg_monthly": FetcherConfig(
        fn=fetch_tw_moea_nationwide_avg,
        fallback_date=date(2003, 1, 1),
        source_name="Taiwan MOEA Energy Administration — Nationwide Average",
        country="Taiwan, China",
        homepage="https://www2.moeaea.gov.tw/oil111/EN/NationwideAvg",
        cadence="monthly",
        full_refresh=True,
    ),
    "tw_cpc_history_prices": FetcherConfig(
        fn=fetch_tw_cpc_history_prices,
        fallback_date=date(2020, 1, 1),
        source_name="CPC Corp Taiwan — Historical Retail Prices",
        country="Taiwan, China",
        homepage="https://www.cpc.com.tw/en/HistoryPrice.aspx?n=3058",
        cadence="weekly",
        full_refresh=True,
    ),
    # ── Tonga ─────────────────────────────────────────────────────────────────
    "to_mted_petroleum_prices_monthly": FetcherConfig(
        fn=fetch_to_mted_petroleum_prices,
        fallback_date=date(2020, 1, 1),
        source_name="Tonga MTED Petroleum Price Notices",
        country="Tonga",
        homepage="https://www.mted.gov.to/",
        cadence="monthly",
    ),
    # ── Pacific Islands ───────────────────────────────────────────────────────
    "pg_iccc_monthly_irp": FetcherConfig(
        fn=fetch_png_iccc,
        fallback_date=date(2023, 1, 1),
        source_name="Papua New Guinea ICCC Indicative Retail Fuel Prices",
        country="Papua New Guinea",
        homepage="https://iccc.gov.pg/prices-regulation/#fuel-prices",
        cadence="monthly",
        full_refresh=True,
    ),
    "ws_mof_monthly_fuel_prices": FetcherConfig(
        fn=fetch_samoa_mof,
        fallback_date=date(2023, 1, 1),
        source_name="Samoa Ministry of Finance — Monthly Fuel Prices",
        country="Samoa",
        homepage="https://www.mof.gov.ws/press-releases/",
        cadence="monthly",
    ),
    "vu_doe_retail_petrol_diesel_2025": FetcherConfig(
        fn=fetch_vanuatu_doe,
        fallback_date=date(2023, 1, 1),
        source_name="Vanuatu Department of Energy — Retail Fuel Prices",
        country="Vanuatu",
        homepage="https://doe.gov.vu/index.php/news-events/news",
        cadence="irregular",
    ),
    "sb_price_control_petroleum_2025": FetcherConfig(
        fn=fetch_solomon_islands,
        fallback_date=date(2023, 1, 1),
        source_name="Solomon Islands Government Price Control — Petroleum",
        country="Solomon Islands",
        homepage="https://solomons.gov.sb/",
        cadence="irregular",
    ),
    "sb_price_control_lpg_2025": FetcherConfig(
        fn=fetch_solomon_islands,
        fallback_date=date(2023, 1, 1),
        source_name="Solomon Islands Government Price Control — LPG",
        country="Solomon Islands",
        homepage="https://solomons.gov.sb/",
        cadence="irregular",
    ),
    # ── Philippines ───────────────────────────────────────────────────────────
    "ph_doe_retail_pump_prices": FetcherConfig(
        fn=fetch_philippines_doe,
        fallback_date=date(2024, 1, 1),
        source_name="Philippines DOE Retail Pump Prices",
        country="Philippines",
        homepage="https://doe.gov.ph/site/vfo/articles/group/liquid-fuels",
        cadence="manual",  # PDF-based scraper stale since 2025-09-08; requires manual review
    ),
    "ph_doe_visayas_weekly": FetcherConfig(
        fn=fetch_ph_doe_visayas,
        fallback_date=date(2020, 1, 1),
        source_name="Philippines DOE Visayas Weekly Price Monitoring",
        country="Philippines",
        homepage="https://doe.gov.ph/site/vfo/articles/group/liquid-fuels",
        cadence="weekly",
    ),
    # ── Thailand ──────────────────────────────────────────────────────────────
    "th_eppo_p04_monthly": FetcherConfig(
        fn=fetch_th_eppo_p04,
        fallback_date=date(2020, 1, 1),
        source_name="Thailand EPPO Table P04 — Monthly Retail Petroleum Prices",
        country="Thailand",
        homepage="https://www.eppo.go.th/index.php/en/en-energystatistics/petroleum-statistic",
        cadence="monthly",
        full_refresh=True,
    ),
    "th_eppo_retail_daily": FetcherConfig(
        fn=fetch_th_eppo_retail_daily,
        fallback_date=date(2024, 1, 1),
        source_name="Thailand EPPO Retail Fuel Prices (Daily)",
        country="Thailand",
        homepage="http://www.eppo.go.th/petro/price/index.html",
        cadence="daily",
    ),
    "th_or_pttor_current_oil_price_daily": FetcherConfig(
        fn=fetch_th_or_pttor_current_oil_price,
        fallback_date=date(2024, 1, 1),
        source_name="OR (PTT Oil & Retail) Current Oil Prices",
        country="Thailand",
        homepage="https://www.pttor.com/en/for-driver",
        cadence="daily",
    ),
    "th_eppo_ngv_bangkok_2025": FetcherConfig(
        fn=fetch_thailand_eppo_ngv,
        fallback_date=date(2023, 1, 1),
        source_name="Thailand EPPO NGV Bangkok Retail Prices",
        country="Thailand",
        homepage="https://www.eppo.go.th/index.php/en/en-energystatistics/petroleum-statistic",
        cadence="irregular",
    ),
    "th_bangchak_retail_history": FetcherConfig(
        fn=fetch_th_bangchak_retail_history,
        fallback_date=date(2015, 1, 1),
        source_name="Bangchak Historical Retail Oil Prices",
        country="Thailand",
        homepage="https://www.bangchak.co.th/en/oilprice/historical",
        cadence="irregular",
    ),
    # ── Timor-Leste ───────────────────────────────────────────────────────────
    "tl_anp_daily_fuel_price": FetcherConfig(
        fn=fetch_timor_anp,
        fallback_date=date(2024, 1, 1),
        source_name="Timor-Leste ANP Daily Fuel Price",
        country="Timor-Leste",
        homepage="https://www.anp.tl/daily-fuel-price/",
        cadence="daily",
    ),
    # ── China ─────────────────────────────────────────────────────────────────
    "cn_ndrc_max_retail_prices_biweekly": FetcherConfig(
        fn=fetch_cn_ndrc_max_retail_prices,
        fallback_date=date(2024, 1, 1),
        source_name="China NDRC — Maximum Retail Prices (Gasoline/Diesel)",
        country="China",
        homepage="https://www.ndrc.gov.cn/xwdt/xwfb/",
        cadence="irregular",
    ),
    # ── Vietnam ───────────────────────────────────────────────────────────────
    "vn_petrolimex_retail": FetcherConfig(
        fn=fetch_vn_petrolimex,
        fallback_date=date(2019, 12, 31),
        source_name="Petrolimex Vietnam Retail Price Announcements",
        country="Vietnam",
        homepage="https://www.petrolimex.com.vn/ndi/thong-cao-bao-chi.html",
        cadence="irregular",
    ),
    # ── Global commodities ────────────────────────────────────────────────────
    "global_investing_daily": FetcherConfig(
        fn=fetch_investing_commodities,
        fallback_date=date(2015, 1, 1),
        source_name="Investing.com Commodity Futures",
        country="Global",
        homepage="https://www.investing.com/commodities/",
        cadence="daily",
    ),
}

__all__ = ["FETCHER_REGISTRY", "FetcherConfig", "Cadence"]
