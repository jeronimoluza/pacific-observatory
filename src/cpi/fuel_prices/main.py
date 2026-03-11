"""CLI entry point for the fuel_prices module.

Usage:
    python -m src.cpi.fuel_prices fetch                            # all sources
    python -m src.cpi.fuel_prices fetch --source au_aip_tgp_weekly # one source
    python -m src.cpi.fuel_prices migrate                          # one-time fixes
    python -m src.cpi.fuel_prices visualize                        # regenerate HTML
    python -m src.cpi.fuel_prices backfill-fuelcheck --overwrite    # full FuelCheck history
"""

import argparse
import sys
from collections.abc import Callable
from datetime import date
from typing import cast

import pandas as pd

from .constants import COLUMNS, PRIMARY_CSV, PROJECT_ROOT
from .fetchers import FETCHER_REGISTRY
from .fetchers.korea import fetch_kr_fuel_news_evidence
from .fetchers.thailand import fetch_thailand_news_evidence
from .fixes import run_all_fixes
from .backfill_fuelcheck import backfill_nsw_fuelcheck
from .loader import (
    get_cutoff,
    load_fuel_data,
    merge_new_rows,
    read_fetch_state,
    write_fetch_state,
)
from .storage import source_csv_path
from .visualize import gen_fuel_html
from .visualize_policy import gen_policy_html, load_policy_data

# source keys whose rows in the secondary CSV are dropped + replaced on each full-refresh fetch
_FULL_REFRESH_KEYS = {
    sk for sk, (_, _, full_refresh) in FETCHER_REGISTRY.items() if full_refresh
}

# Global commodity benchmark sources → commodity_prices.csv
_COMMODITY_SOURCES = {
    "global_investing_daily",
    "global_eia_spot_daily",
    "global_wb_pinksheet",
    "global_imf_fred_monthly",
}

# Maps each fetcher fn to its canonical output CSV (secondary for "second" sources)
_SECONDARY_SOURCES = {
    "au_aip_tgp_weekly",
    "au_fuelwatch_perth_daily",
    "kh_ptt_monthly_prices",
    "fj_fccc_order_prices",
    "id_oto_monthly_prices",
    "id_pertamina_pengumuman_non_subsidi",
    "jp_anre_weekly_petroleum_2026",
    "ph_doe_visayas_weekly",
    "mn_nso_aimag_weekly_fuel",
    "nz_mbie_weekly_fuel",
    "kr_opinet_history_weekly",
    "kr_opinet_daily_avg",
    "th_eppo_p04_monthly",
    "th_eppo_retail_daily",
    "th_or_pttor_current_oil_price_daily",
    "vn_petrolimex_retail",
}


def _load_csv(path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame(columns=pd.Index(COLUMNS))


def _save_csv(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS].to_csv(path, index=False)
    print(f"  Saved {len(df):,} rows → {path}")


def cmd_fetch(args) -> None:
    """Fetch new data from one or all sources.

    Writes per-source CSVs under:
      data/cpi/fuel_prices/<country_slug>/<source_key>/observations.csv
    """
    state = read_fetch_state()

    if args.source:
        if args.source not in FETCHER_REGISTRY:
            print(f"Unknown source key: {args.source}")
            print(f"Available: {', '.join(sorted(FETCHER_REGISTRY))}")
            sys.exit(1)
        keys_to_run = [args.source]
    else:
        keys_to_run = list(FETCHER_REGISTRY)

    # Group by fetcher fn so shared fetchers run once.
    fn_to_keys: dict[Callable[[date], pd.DataFrame], list[str]] = {}
    for sk in keys_to_run:
        fn = cast(Callable[[date], pd.DataFrame], FETCHER_REGISTRY[sk][0])
        fn_to_keys.setdefault(fn, []).append(sk)

    # Cache existing per-source CSVs within this run.
    existing_cache: dict[str, pd.DataFrame] = {}

    for fn, fn_keys in fn_to_keys.items():
        # Use the earliest cutoff among keys sharing this fetcher to avoid missing
        # rows for siblings.
        cutoffs: list[date] = []
        for sk in fn_keys:
            _fn, fallback, _full_refresh = FETCHER_REGISTRY[sk]
            cutoffs.append(get_cutoff(state, sk, fallback))
        cutoff = min(cutoffs) if cutoffs else date(1900, 1, 1)

        keys_label = ", ".join(fn_keys)
        print(f"\n--- {keys_label} (cutoff: {cutoff}) ---")
        try:
            new_df = fn(cutoff)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        if new_df is None or new_df.empty:
            print("  No new rows")
            continue

        if "country" not in new_df.columns:
            new_df = new_df.copy()
            new_df["country"] = "Unknown"
        if "source_key" not in new_df.columns:
            # Best-effort fallback: treat this fetch as belonging to the first key.
            new_df = new_df.copy()
            new_df["source_key"] = fn_keys[0]

        # Write each (country, source_key) group into its own CSV.
        for key, grp in new_df.groupby(["country", "source_key"], dropna=False):
            country_raw, sk_raw = cast(tuple[object, object], key)
            country = str(country_raw) if country_raw is not None else "Unknown"
            sk = str(sk_raw) if sk_raw is not None else fn_keys[0]
            out_path = source_csv_path(country, sk)
            cache_key = str(out_path)

            if cache_key in existing_cache:
                existing = existing_cache[cache_key]
            else:
                existing = _load_csv(out_path)
                existing_cache[cache_key] = existing

            full_refresh = False
            if sk in FETCHER_REGISTRY:
                full_refresh = bool(FETCHER_REGISTRY[sk][2])
            if full_refresh:
                existing = pd.DataFrame(columns=pd.Index(COLUMNS))

            merged = merge_new_rows(existing, grp)
            existing_cache[cache_key] = merged
            _save_csv(merged, out_path)

        # Update fetch state with max observation_date per source_key in new rows
        if "observation_date" in new_df.columns:
            for sk, sk_df in new_df.groupby("source_key"):
                max_date_str = sk_df["observation_date"].dropna().max()
                missing = pd.isna(max_date_str)
                if max_date_str is None or (isinstance(missing, bool) and missing):
                    continue
                try:
                    state[str(sk)] = date.fromisoformat(str(max_date_str))
                except (ValueError, TypeError):
                    continue

    write_fetch_state(state)
    print("\nDone.")


def cmd_migrate(args) -> None:
    """Apply one-time data-quality fixes to the primary CSV."""
    df = _load_csv(PRIMARY_CSV)
    if df.empty:
        print("Primary CSV is empty or does not exist.")
        return
    print(f"Loaded {len(df):,} rows from {PRIMARY_CSV}")
    df_fixed = run_all_fixes(df)
    added = len(df_fixed) - len(df)
    _save_csv(df_fixed, PRIMARY_CSV)
    print(f"Migration complete ({added:+d} rows).")


def cmd_policy(args) -> None:
    """Regenerate fuel_policy_overview.html from current data files."""
    from .constants import DATA_DIR

    out = DATA_DIR / "fuel_policy_overview.html"
    print("Loading policy data...")
    data = load_policy_data()
    print("Loading fuel prices data...")
    fuel_data = load_fuel_data()
    print(f"Generating HTML \u2192 {out}")
    gen_policy_html(data, fuel_data, out)
    print("Done.")


def cmd_th_news(args) -> None:
    """Collect Thailand EPPO oil price news evidence (Track A)."""
    from .track_a_artifacts import write_news_evidence_artifact

    print("Fetching Thailand news evidence RSS feed...")
    records = fetch_thailand_news_evidence(max_items=args.max_items)
    if not records:
        print("No news items fetched.")
        return

    result = write_news_evidence_artifact(
        records=records,
        project_root=PROJECT_ROOT,
        country_slug="thailand",
        artifact_name="th_eppo_oil_price_status_news",
        source_url=records[0].get("source_url") or "",
        producer="src/cpi/fuel_prices/main.py",
    )
    print(f"Saved {len(records)} records → {result['artifact_path']}")


def cmd_kr_news(args) -> None:
    """Collect Korea fuel price news evidence (Track A)."""
    from .track_a_artifacts import write_news_evidence_artifact

    print("Fetching Korea news evidence RSS feed...")
    records = fetch_kr_fuel_news_evidence(max_items=args.max_items)
    if not records:
        print("No news items fetched.")
        return

    result = write_news_evidence_artifact(
        records=records,
        project_root=PROJECT_ROOT,
        country_slug="korea",
        artifact_name="kr_fuel_price_news",
        source_url=records[0].get("source_url") or "",
        producer="src/cpi/fuel_prices/main.py",
    )
    print(f"Saved {len(records)} records → {result['artifact_path']}")


def cmd_visualize(args) -> None:
    """Regenerate fuel_prices.html from the current CSVs."""
    from .constants import DATA_DIR

    out = DATA_DIR / "fuel_prices.html"
    print("Loading data...")
    all_data = load_fuel_data()
    print(f"Generating HTML → {out}")
    gen_fuel_html(all_data, out)
    print("Done.")


def cmd_backfill_fuelcheck(args) -> None:
    """Download and write all NSW FuelCheck price history."""

    def _parse_period(s: str | None) -> tuple[int, int] | None:
        if not s:
            return None
        s = str(s).strip()
        if not s:
            return None
        parts = s.split("-")
        if len(parts) != 2:
            raise ValueError("Expected YYYY-MM")
        return int(parts[0]), int(parts[1])

    out_path = backfill_nsw_fuelcheck(
        overwrite=bool(args.overwrite),
        from_period=_parse_period(getattr(args, "from_period", None)),
        to_period=_parse_period(getattr(args, "to_period", None)),
    )
    print(f"Done. Wrote FuelCheck history → {out_path}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.cpi.fuel_prices",
        description="Pacific Observatory Fuel Prices CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch new data from official sources")
    p_fetch.add_argument(
        "--source", metavar="SOURCE_KEY", help="Fetch a single source key only"
    )
    p_fetch.set_defaults(func=cmd_fetch)

    # migrate
    p_migrate = sub.add_parser("migrate", help="Apply one-time data-quality fixes")
    p_migrate.set_defaults(func=cmd_migrate)

    # fuelcheck backfill
    p_fc = sub.add_parser(
        "backfill-fuelcheck",
        help="Backfill NSW FuelCheck monthly resources into one observations.csv",
    )
    p_fc.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing data/cpi/fuel_prices/australia/au_nsw_fuelcheck_history/observations.csv",
    )
    p_fc.add_argument(
        "--from",
        dest="from_period",
        help="Only process periods >= YYYY-MM (disables resume skip)",
    )
    p_fc.add_argument(
        "--to",
        dest="to_period",
        help="Only process periods <= YYYY-MM",
    )
    p_fc.set_defaults(func=cmd_backfill_fuelcheck)

    # visualize
    p_vis = sub.add_parser("visualize", help="Regenerate fuel_prices.html")
    p_vis.set_defaults(func=cmd_visualize)

    # policy
    p_pol = sub.add_parser("policy", help="Regenerate fuel_policy_overview.html")
    p_pol.set_defaults(func=cmd_policy)

    # track-a news evidence
    p_news = sub.add_parser(
        "tracka-news", help="Collect Track A Thailand news evidence"
    )
    p_news.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Max RSS items to collect (default: 50)",
    )
    p_news.set_defaults(func=cmd_th_news)

    p_kr_news = sub.add_parser(
        "tracka-news-kr", help="Collect Track A Korea news evidence"
    )
    p_kr_news.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Max RSS items to collect (default: 50)",
    )
    p_kr_news.set_defaults(func=cmd_kr_news)

    parsed = parser.parse_args(argv)
    parsed.func(parsed)


if __name__ == "__main__":
    main()
