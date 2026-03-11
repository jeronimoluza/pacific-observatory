"""CLI entry point for the fuel_prices module.

Usage:
    python -m src.cpi.fuel_prices fetch                            # all sources
    python -m src.cpi.fuel_prices fetch --source au_aip_tgp_weekly # one source
    python -m src.cpi.fuel_prices migrate                          # one-time fixes
    python -m src.cpi.fuel_prices visualize                        # regenerate HTML
"""

import argparse
import sys
from datetime import date

import pandas as pd

from .constants import COLUMNS, COMMODITY_CSV, PRIMARY_CSV, PROJECT_ROOT, SECONDARY_CSV
from .fetchers import FETCHER_REGISTRY
from .fetchers.korea import fetch_kr_fuel_news_evidence
from .fetchers.thailand import fetch_thailand_news_evidence
from .fixes import run_all_fixes
from .loader import (
    get_cutoff,
    load_fuel_data,
    merge_new_rows,
    read_fetch_state,
    write_fetch_state,
)
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
    return pd.DataFrame(columns=COLUMNS)


def _save_csv(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS].to_csv(path, index=False)
    print(f"  Saved {len(df):,} rows → {path}")


def cmd_fetch(args) -> None:
    """Fetch new data from one or all sources."""
    state = read_fetch_state()

    if args.source:
        if args.source not in FETCHER_REGISTRY:
            print(f"Unknown source key: {args.source}")
            print(f"Available: {', '.join(sorted(FETCHER_REGISTRY))}")
            sys.exit(1)
        keys_to_run = [args.source]
    else:
        keys_to_run = list(FETCHER_REGISTRY)

    # Deduplicate: if multiple source keys share the same fetcher fn, run once.
    seen_fns: set = set()
    deduped_keys: list[str] = []
    for sk in keys_to_run:
        fn = FETCHER_REGISTRY[sk][0]
        fn_id = id(fn)
        if fn_id not in seen_fns:
            seen_fns.add(fn_id)
            deduped_keys.append(sk)

    df_primary = _load_csv(PRIMARY_CSV)
    df_secondary = _load_csv(SECONDARY_CSV)
    df_commodity = _load_csv(COMMODITY_CSV)

    primary_changed = False
    secondary_changed = False
    commodity_changed = False

    for sk in deduped_keys:
        fn, fallback, full_refresh = FETCHER_REGISTRY[sk]
        cutoff = get_cutoff(state, sk, fallback)

        print(f"\n--- {sk} (cutoff: {cutoff}) ---")
        try:
            new_df = fn(cutoff)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        if new_df is None or new_df.empty:
            print("  No new rows")
            continue

        # Determine target CSV
        is_commodity = sk in _COMMODITY_SOURCES
        is_secondary = sk in _SECONDARY_SOURCES
        if is_commodity:
            target_df = df_commodity
        elif is_secondary:
            target_df = df_secondary
        else:
            target_df = df_primary

        # Full-refresh: drop stale rows for this source key before merging
        if full_refresh and not target_df.empty and "source_key" in target_df.columns:
            # Collect all source_keys from the new data (a single fetcher may return multiple)
            new_source_keys = (
                set(new_df["source_key"].dropna().unique())
                if "source_key" in new_df.columns
                else {sk}
            )
            target_df = target_df[~target_df["source_key"].isin(new_source_keys)].copy()

        merged = merge_new_rows(target_df, new_df)

        if is_commodity:
            df_commodity = merged
            commodity_changed = True
        elif is_secondary:
            df_secondary = merged
            secondary_changed = True
        else:
            df_primary = merged
            primary_changed = True

        # Update fetch state with max observation_date from new rows
        if "observation_date" in new_df.columns:
            max_date_str = new_df["observation_date"].dropna().max()
            if max_date_str:
                try:
                    new_max = date.fromisoformat(str(max_date_str))
                    state[sk] = new_max
                    # Also update sibling source_keys that share this fetcher
                    if "source_key" in new_df.columns:
                        for sibling_sk in keys_to_run:
                            if FETCHER_REGISTRY[sibling_sk][0] is fn:
                                sibling_rows = new_df[
                                    new_df["source_key"] == sibling_sk
                                ]
                                if not sibling_rows.empty:
                                    sib_max = (
                                        sibling_rows["observation_date"].dropna().max()
                                    )
                                    if sib_max:
                                        state[sibling_sk] = date.fromisoformat(
                                            str(sib_max)
                                        )
                except (ValueError, TypeError):
                    pass

    if primary_changed:
        _save_csv(df_primary, PRIMARY_CSV)
    if secondary_changed:
        _save_csv(df_secondary, SECONDARY_CSV)
    if commodity_changed:
        _save_csv(df_commodity, COMMODITY_CSV)

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
