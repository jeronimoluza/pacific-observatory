"""``po fuel regime-check``: deterministic alerts against the regime table.

Writes ``outputs/fuel/regime_alerts/<YYYY-MM-DD>.csv`` (spec
``2026-10-16-regime-table.md`` §6). It never edits ``regimes.yaml``: an alert
is a question for the ``update-fuel-price-regimes`` skill and a human.

Detectors:

- ``data``: price changes observed in the last 365 days per published series
  vs the row in force today (rules below), plus ``publication: announcement``
  sources against a ``formula``/``market`` row.
- ``expiry``: the row in force has ``temporary_until`` or ``valid_to`` within
  ``EXPIRY_DAYS`` (or past), or its text names a temporary measure but no
  ``temporary_until`` is set.
- ``unsigned``: ``reviewer: agent:claude`` rows reviewed more than
  ``UNSIGNED_DAYS`` ago.
- ``stale_seed``: a ``wb2024``/``override`` row in force that a ``data`` alert
  contradicts.
- ``text`` and ``web``: TODO hooks (§6.2, §6.3), not implemented.

Daily hook: ``po fuel watch`` (branch mvp/fuel-watch) can call
``run_regime_check()`` after its own checks; it returns the CSV path and the
alerts frame.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .fill_rule import ALIVE_DAYS, CADENCE_DAYS
from .reference.subsidies import TABLE_PRODUCTS
from .regimes import REGIMES_PATH, load_regimes, regime_at

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = _PROJECT_ROOT / "outputs" / "fuel"
STATUS_DIR = _PROJECT_ROOT / "data" / "fuel" / "_status"
ALERTS_DIRNAME = "regime_alerts"

COLUMNS = [
    "detected_at",
    "detector",
    "iso3",
    "product",
    "current_regime",
    "current_adjust_freq",
    "implied_regime",
    "implied_adjust_freq",
    "implied_subsidy",
    "signal",
    "evidence_url",
    "evidence_sha256",
    "evidence_quote",
    "ref",
]

WINDOW_DAYS = 365
CHANGE_TOL = 0.001  # relative change that counts as a price change
ADMIN_MAX_CHANGES = 24  # administered / frozen with >= this many: not administered
FORMULA_WEEKLY_MIN = 6  # weekly formula with fewer: not a weekly formula
MARKET_MAX = {"daily": 12, "weekly": 6}  # market with <= this: looks held
MARKET_MAX_OTHER = 2
ZERO_ALIVE_DAYS = 180  # 0 changes while the source has been alive this long
EXPIRY_DAYS = 14
UNSIGNED_DAYS = 7
SEED_PROVENANCES = {"wb2024", "override"}
_FAMILY_TO_PRODUCT = {p.lower(): p for p in TABLE_PRODUCTS}
_TEMPORARY_RE = re.compile(
    r"temporar|\bexpir|\bextension|\bextended|\bprórroga|\bprorroga|\bvence"
    r"|\bran to\b|\bruns? to\b|\buntil\b|\bfor \d+ (?:days|weeks|months)\b",
    re.IGNORECASE,
)


def _implied_freq(n_changes: int) -> str:
    """Adjust frequency a count of changes in 365 days looks like."""
    if n_changes == 0:
        return "frozen"
    if n_changes >= 200:
        return "daily"
    if n_changes >= 40:
        return "weekly"
    if n_changes >= 20:
        return "biweekly"
    return "monthly" if n_changes >= 6 else "adhoc"


def _last_ok(status_dir: Path) -> dict[str, pd.Timestamp]:
    """source_key -> last collect without errors, over every region status."""
    out: dict[str, pd.Timestamp] = {}
    for path in sorted(status_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key, ts in (data.get("last_ok") or {}).items():
            out[key] = pd.Timestamp(str(ts)[:10])
    return out


def series_changes(outputs_dir: Path, today: pd.Timestamp) -> pd.DataFrame:
    """One row per published (iso3, product, series_key): real observations
    (never forward-filled ones) and price changes in the last 365 days."""
    rows = []
    start = today - pd.Timedelta(days=WINDOW_DAYS)
    for csv_path in sorted(outputs_dir.rglob("fuel_product_local_prices.csv")):
        df = pd.read_csv(csv_path, low_memory=False)
        if df.empty or "fuel_family" not in df:
            continue
        if "is_forward_filled" in df:
            df = df[~df["is_forward_filled"].astype(str).str.lower().eq("true")]
        df = df.assign(
            product=df["fuel_family"].astype(str).str.lower().map(_FAMILY_TO_PRODUCT),
            date=pd.to_datetime(df["observation_date"].astype(str).str[:10]),
            source=df["source_key"].astype(str).str.split(",").str[0],
        )
        df = df[df["product"].notna() & df["price_local"].notna()]
        for (iso3, product, skey), g in df.groupby(["iso3", "product", "series_key"]):
            g = g.sort_values("date").drop_duplicates("date", keep="last")
            w = g[(g["date"] > start) & (g["date"] <= today)]
            n_chg = int((w["price_local"].pct_change().abs() > CHANGE_TOL).sum())
            rows.append(
                {
                    "iso3": iso3,
                    "product": product,
                    "series_key": skey,
                    "label": str(g["label"].iloc[-1]) if "label" in g else skey,
                    "source_key": str(g["source"].iloc[-1]),
                    "first_obs": g["date"].min(),
                    "last_obs": g["date"].max(),
                    "obs_365": len(w),
                    "changes_365": n_chg,
                }
            )
    return pd.DataFrame(rows)


def _alert(today, detector, row, **kw) -> dict:
    out = dict.fromkeys(COLUMNS, "")
    out.update(
        detected_at=today.date().isoformat(),
        detector=detector,
        iso3=row["iso3"],
        product=row["product"],
        current_regime=row.get("regime", "") or "",
        current_adjust_freq=_s(row.get("adjust_freq")),
    )
    out.update(kw)
    return out


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def detect_data(
    table: pd.DataFrame,
    series: pd.DataFrame,
    registry: dict[str, dict],
    last_ok: dict[str, pd.Timestamp],
    today: pd.Timestamp,
) -> list[dict]:
    """§6.1: observed changes in 365 days vs the row in force today."""
    alerts: list[dict] = []
    seen_announce: set[tuple[str, str, str]] = set()
    for s in series.itertuples(index=False):
        row = regime_at(table, s.iso3, s.product, today.date())
        if row is None:
            continue
        src = registry.get(s.source_key, {})
        cadence = src.get("cadence") or "irregular"
        url = _s(src.get("url"))
        ref = (
            f"{s.source_key}:{s.series_key} changes_365={s.changes_365} "
            f"obs_365={s.obs_365} last_obs={s.last_obs.date()} cadence={cadence}"
        )
        regime, freq, n = row["regime"], _s(row["adjust_freq"]), s.changes_365

        if src.get("publication") == "announcement" and regime in ("formula", "market"):
            key = (s.iso3, s.product, s.source_key)
            if key not in seen_announce:
                seen_announce.add(key)
                alerts.append(
                    _alert(
                        today,
                        "data",
                        row,
                        evidence_url=url,
                        ref=ref,
                        signal=f"source {s.source_key} is publication=announcement "
                        f"but the row is {regime}: one of the two is wrong",
                    )
                )

        ok = last_ok.get(s.source_key)
        if ok is not None:
            alive = (today - ok).days <= ALIVE_DAYS
        else:
            horizon = max(ALIVE_DAYS, 2 * CADENCE_DAYS.get(cadence, 92))
            alive = (today - s.last_obs).days <= horizon
        if not alive:
            continue

        implied, signal = None, None
        if (regime == "administered" or freq == "frozen") and n >= ADMIN_MAX_CHANGES:
            implied = "formula"
            signal = f"{regime}/{freq or '-'} but {n} changes in 365 d (>= {ADMIN_MAX_CHANGES})"
        elif regime == "formula" and freq == "weekly" and n < FORMULA_WEEKLY_MIN:
            implied = "administered"
            signal = f"weekly formula but {n} changes in 365 d (< {FORMULA_WEEKLY_MIN})"
        elif regime == "market" and n <= MARKET_MAX.get(cadence, MARKET_MAX_OTHER):
            lim = MARKET_MAX.get(cadence, MARKET_MAX_OTHER)
            implied = "administered"
            signal = f"market but {n} changes in 365 d at {cadence} cadence (<= {lim})"
        elif (
            n == 0
            and (today - s.first_obs).days > ZERO_ALIVE_DAYS
            and not (regime == "administered" and freq == "frozen")
        ):
            implied = "administered"
            signal = f"0 changes in 365 d; source alive > {ZERO_ALIVE_DAYS} d"
        if implied:
            alerts.append(
                _alert(
                    today,
                    "data",
                    row,
                    implied_regime=implied,
                    implied_adjust_freq=_implied_freq(n),
                    signal=signal,
                    evidence_url=url,
                    ref=ref,
                )
            )
    return alerts


def detect_expiry(table: pd.DataFrame, today: pd.Timestamp) -> list[dict]:
    """Temporary rows in force that end within ``EXPIRY_DAYS`` or already did,
    temporary-sounding rows without ``temporary_until``, and cells whose last
    row expired with nothing after it."""
    alerts: list[dict] = []
    soon = today + pd.Timedelta(days=EXPIRY_DAYS)
    for (iso3, product), cell in table.groupby(["iso3", "product"]):
        row = regime_at(table, iso3, product, today.date())
        if row is None:
            ended = cell[cell["valid_to"].notna() & (cell["valid_to"] < today)]
            if not ended.empty:
                last = ended.sort_values("valid_to").iloc[-1].to_dict()
                alerts.append(
                    _alert(
                        today,
                        "expiry",
                        last,
                        signal=f"valid_to {last['valid_to'].date()} passed and no row is in force",
                        evidence_url=_s(last["evidence_url"]),
                        ref=f"valid_from={_s(last['valid_from'])[:10]}",
                    )
                )
            continue
        ref = f"valid_from={_s(row['valid_from'])[:10]} provenance={row['provenance']}"
        common = dict(
            evidence_url=_s(row["evidence_url"]),
            evidence_sha256=_s(row["evidence_sha256"]),
            evidence_quote=_s(row["evidence_quote"]),
            ref=ref,
        )
        for col in ("temporary_until", "valid_to"):
            end = row[col]
            if pd.notna(end) and end <= soon:
                days = (end - today).days
                when = f"expired {-days} d ago" if days < 0 else f"ends in {days} d"
                alerts.append(
                    _alert(
                        today,
                        "expiry",
                        row,
                        signal=f"{col} {end.date()}: {when}",
                        **common,
                    )
                )
                break
        else:
            text = " ".join(
                _s(row[c]) for c in ("note", "subsidy_note", "evidence_quote")
            )
            hit = _TEMPORARY_RE.search(text)
            if pd.isna(row["temporary_until"]) and pd.isna(row["valid_to"]) and hit:
                alerts.append(
                    _alert(
                        today,
                        "expiry",
                        row,
                        signal=f"text names a temporary measure ('{hit.group(0)}') "
                        "but temporary_until is not set",
                        **common,
                    )
                )
    return alerts


def detect_unsigned(table: pd.DataFrame, today: pd.Timestamp) -> list[dict]:
    """Agent-proposed rows still unsigned ``UNSIGNED_DAYS`` after review."""
    alerts = []
    agent = table[table["reviewer"].astype(str).eq("agent:claude")]
    for row in agent.to_dict("records"):
        reviewed = pd.to_datetime(row["reviewed_at"], errors="coerce")
        if pd.isna(reviewed) or (today - reviewed).days > UNSIGNED_DAYS:
            age = "unknown" if pd.isna(reviewed) else f"{(today - reviewed).days} d"
            alerts.append(
                _alert(
                    today,
                    "unsigned",
                    row,
                    signal=f"reviewer agent:claude, unsigned for {age}",
                    evidence_url=_s(row["evidence_url"]),
                    ref=f"valid_from={_s(row['valid_from'])[:10]} reviewed_at={_s(row['reviewed_at'])}",
                )
            )
    return alerts


def detect_stale_seed(
    table: pd.DataFrame, data_alerts: list[dict], today: pd.Timestamp
) -> list[dict]:
    """Seed rows (wb2024 / override) in force that a data alert contradicts;
    one alert per cell."""
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for a in data_alerts:
        if a["implied_regime"]:
            by_cell.setdefault((a["iso3"], a["product"]), []).append(a)
    alerts = []
    for (iso3, product), hits in sorted(by_cell.items()):
        row = regime_at(table, iso3, product, today.date())
        if row is None or row["provenance"] not in SEED_PROVENANCES:
            continue
        alerts.append(
            _alert(
                today,
                "stale_seed",
                row,
                implied_regime=hits[0]["implied_regime"],
                implied_adjust_freq=hits[0]["implied_adjust_freq"],
                signal=f"{row['provenance']} row contradicted by data: "
                + "; ".join(h["signal"] for h in hits),
                evidence_url=hits[0]["evidence_url"],
                ref=" | ".join(h["ref"] for h in hits),
            )
        )
    return alerts


def detect_text(table: pd.DataFrame, today: pd.Timestamp) -> list[dict]:
    """TODO (spec §6.2): cross ``regime_effect`` from policy_discovery /
    update-fuel-crisis-policy workbook rows against ``regime_at``. Needs the
    structured extraction first; returns nothing until then."""
    return []


def detect_web(table: pd.DataFrame, today: pd.Timestamp) -> list[dict]:
    """TODO (spec §6.3): regulator-page changes and regime-term news from
    ``po fuel watch`` (pages / news / GPP). Returns nothing until wired."""
    return []


def run_regime_check(
    today: date | None = None,
    outputs_dir: Path = OUTPUTS_DIR,
    status_dir: Path = STATUS_DIR,
    table_path: Path = REGIMES_PATH,
) -> tuple[Path, pd.DataFrame]:
    """Run every detector and write ``<outputs_dir>/regime_alerts/<date>.csv``."""
    from .config import build_fuel_registry

    today_ts = pd.Timestamp(today or datetime.now(timezone.utc).date())
    table = load_regimes(table_path)
    registry = build_fuel_registry()
    series = series_changes(outputs_dir, today_ts)
    logger.info("regime-check: %d published series", len(series))
    data = (
        detect_data(table, series, registry, _last_ok(status_dir), today_ts)
        if not series.empty
        else []
    )
    alerts = (
        data
        + detect_expiry(table, today_ts)
        + detect_unsigned(table, today_ts)
        + detect_stale_seed(table, data, today_ts)
        + detect_text(table, today_ts)
        + detect_web(table, today_ts)
    )
    df = pd.DataFrame(alerts, columns=COLUMNS)
    out = outputs_dir / ALERTS_DIRNAME / f"{today_ts.date().isoformat()}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out, df
