"""Per-region run status and publish gates for the weekly fuel run.

``data/fuel/_status/<region>.json`` holds the last collect's failed sources
and the last publish's outcome. Publish blocks when fewer countries were built
than at the last publish, and alerts (without blocking) on source failures
not listed in the refresh-fuel-dashboards known-failures catalog.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import click

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATUS_DIR = _PROJECT_ROOT / "data" / "fuel" / "_status"
KNOWN_FAILURES = (
    _PROJECT_ROOT
    / ".claude/skills/refresh-fuel-dashboards/references/known_failures.md"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_status(region: str, status_dir: Path = STATUS_DIR) -> dict:
    path = status_dir / f"{region}.json"
    if not path.exists():
        return {"region": region}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_status(status: dict, status_dir: Path) -> Path:
    status_dir.mkdir(parents=True, exist_ok=True)
    path = status_dir / f"{status['region']}.json"
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return path


class FailureRecorder(logging.Handler):
    """Collects the source keys that logged an ERROR while they were running."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.current: str | None = None
        self.failed: dict[str, str] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if self.current and self.current not in self.failed:
            self.failed[self.current] = record.getMessage()[:300]


def record_collect(
    region: str,
    sources_run: list[str],
    failed: dict[str, str],
    status_dir: Path = STATUS_DIR,
) -> Path:
    status = read_status(region, status_dir)
    status["collect"] = {
        "run_ts_utc": _now(),
        "sources_run": len(sources_run),
        "failed_sources": dict(sorted(failed.items())),
    }
    return _write_status(status, status_dir)


def known_failure_patterns(path: Path = KNOWN_FAILURES) -> list[str] | None:
    """Source keys / globs (``autotraveler_*_daily``) named anywhere in the catalog."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\b[a-z][a-z0-9*]*_[a-z0-9_*]+", text)))


def _has_rows(csv_path: Path) -> bool:
    if not csv_path.exists():
        return False
    with open(csv_path, encoding="utf-8") as f:
        f.readline()
        return bool(f.readline().strip())


def countries_with_data(region: str, countries: list[dict]) -> list[str]:
    """Slugs whose fuel_family_usd_prices.csv has rows and that have an enabled source.

    The second condition drops stale outputs left by a disabled source, which
    the build no longer rewrites but publish still discovers.
    """
    from .config import build_fuel_registry

    enabled = {
        e["country_slug"]
        for e in build_fuel_registry(region=region).values()
        if e.get("enabled", True)
    }
    return sorted(
        c["country_slug"]
        for c in countries
        if c["country_slug"] in enabled
        and _has_rows(c["output_dir"] / "fuel_family_usd_prices.csv")
    )


def seed_baseline(
    region: str, countries: list[dict], status_dir: Path = STATUS_DIR
) -> tuple[list[str], Path]:
    """Record the countries with data today as the gate's last_published baseline."""
    with_data = countries_with_data(region, countries)
    status = read_status(region, status_dir)
    status["last_published"] = {
        "run_ts_utc": _now(),
        "countries": with_data,
        "seeded": True,
    }
    return with_data, _write_status(status, status_dir)


def check_publish(
    region: str,
    countries: list[dict],
    *,
    allow_country_drop: bool = False,
    status_dir: Path = STATUS_DIR,
    known_failures: Path = KNOWN_FAILURES,
) -> dict:
    """Run both gates; raise ClickException if the country gate blocks."""
    status = read_status(region, status_dir)
    built = countries_with_data(region, countries)
    last = status.get("last_published") or {}
    prev = last.get("countries")
    gate = {
        "run_ts_utc": _now(),
        "countries_built": len(built),
        "countries": built,
        "previous_countries_built": None if prev is None else len(prev),
        "dropped_countries": sorted(set(prev or []) - set(built)),
        "added_countries": sorted(set(built) - set(prev or [])) if prev else [],
        "override": allow_country_drop,
    }

    failed = sorted((status.get("collect") or {}).get("failed_sources", {}))
    patterns = known_failure_patterns(known_failures)
    if patterns is None:
        logger.warning(
            "Known-failures catalog not found at %s; every failure counts as new",
            known_failures,
        )
        patterns = []
    known = [k for k in failed if any(fnmatch.fnmatchcase(k, p) for p in patterns)]
    gate["failed_sources"] = failed
    gate["known_failures"] = known
    gate["new_failures"] = [k for k in failed if k not in known]
    if gate["new_failures"]:
        logger.warning(
            "[gate] %s: %d source failure(s) not in known_failures.md: %s",
            region,
            len(gate["new_failures"]),
            ", ".join(gate["new_failures"]),
        )

    dropped = prev is not None and len(built) < len(prev)
    if dropped and not allow_country_drop:
        gate["status"] = "blocked"
        gate["color"] = "rojo"
        status["publish"] = gate
        path = _write_status(status, status_dir)
        raise click.ClickException(
            f"[gate] {region}: built {len(built)} countries, last publish had {len(prev)} "
            f"(missing: {', '.join(gate['dropped_countries']) or '-'}). Publish blocked; "
            f"fix the build or rerun with --allow-country-drop. Status: {path}"
        )
    gate["status"] = "published"
    gate["color"] = "amarillo" if (dropped or gate["new_failures"]) else "verde"
    return gate


def record_publish(
    region: str, gate: dict, outputs: dict, status_dir: Path = STATUS_DIR
) -> Path:
    status = read_status(region, status_dir)
    status["publish"] = {**gate, "outputs": {k: str(v) for k, v in outputs.items()}}
    status["last_published"] = {
        "run_ts_utc": gate["run_ts_utc"],
        "countries": gate["countries"],
    }
    return _write_status(status, status_dir)
