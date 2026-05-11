"""Storage status walker for `po text storage-status`.

Split from `storage_tier.py` to keep both files under the 500-line cap.
"""

from datetime import datetime, timezone
from pathlib import Path

from core.config import (
    countries_for_region,
    countries_for_subregion,
    get_country_path,
    resolve_subregion_region,
)
from core.storage_tier import (
    DRIVE_ROOT,
    LOCAL_ROOT,
    _count_news_rows,
    is_drive_online,
)


def _country_news_stats(country_dir: Path) -> tuple[int, str | None]:
    """(total news.csv rows under dir, latest mtime of any news.csv as ISO date)."""
    if not country_dir.exists():
        return 0, None
    rows = 0
    latest: float | None = None
    for f in country_dir.rglob("news.csv"):
        rows += _count_news_rows(f)
        try:
            m = f.stat().st_mtime
        except OSError:
            continue
        if latest is None or m > latest:
            latest = m
    if latest is None:
        return rows, None
    dt = datetime.fromtimestamp(latest, tz=timezone.utc)
    return rows, dt.strftime("%Y-%m-%d")


def _country_state(local_dir: Path, drive_dir: Path, drive_online: bool) -> str:
    local_exists = local_dir.exists() and any(local_dir.rglob("news.csv"))
    drive_exists = (
        drive_online and drive_dir.exists() and any(drive_dir.rglob("news.csv"))
    )

    if not drive_online:
        return "local-only?" if local_exists else "unknown"

    if local_exists and not drive_exists:
        return "local-only"
    if drive_exists and not local_exists:
        return "drive-only"
    if not local_exists and not drive_exists:
        return "absent"

    sources = {p.relative_to(local_dir).parent for p in local_dir.rglob("news.csv")} | {
        p.relative_to(drive_dir).parent for p in drive_dir.rglob("news.csv")
    }
    has_local_newer = False
    has_drive_newer = False
    for s in sources:
        l_path = local_dir / s / "news.csv"
        d_path = drive_dir / s / "news.csv"
        l_rows = _count_news_rows(l_path) if l_path.exists() else 0
        d_rows = _count_news_rows(d_path) if d_path.exists() else 0
        if l_rows > d_rows:
            has_local_newer = True
        elif d_rows > l_rows:
            has_drive_newer = True
    if has_local_newer and has_drive_newer:
        return "mismatch"
    if has_local_newer:
        return "local-newer"
    if has_drive_newer:
        return "drive-newer"
    return "both-equal"


def _enumerate_countries(
    region: str | None,
    subregion: str | None,
    country: str | None,
    drive_online: bool,
) -> list[tuple[str, str, str]]:
    if country is not None:
        r, s, _ = get_country_path(country)
        return [(r, s, country)]

    out: set[tuple[str, str, str]] = set()
    if subregion is not None:
        r = resolve_subregion_region(subregion)
        for c in countries_for_subregion(r, subregion):
            out.add((r, subregion, c))
        for root in (LOCAL_ROOT, DRIVE_ROOT) if drive_online else (LOCAL_ROOT,):
            sub_dir = root / r / subregion
            if sub_dir.is_dir():
                for child in sub_dir.iterdir():
                    if child.is_dir() and not child.name.startswith("_"):
                        out.add((r, subregion, child.name))
        return sorted(out)

    if region is not None:
        for c in countries_for_region(region):
            r_, s_, _ = get_country_path(c)
            out.add((r_, s_, c))
        for root in (LOCAL_ROOT, DRIVE_ROOT) if drive_online else (LOCAL_ROOT,):
            reg_dir = root / region
            if reg_dir.is_dir():
                for sub in reg_dir.iterdir():
                    if sub.is_dir() and not sub.name.startswith("_"):
                        for child in sub.iterdir():
                            if child.is_dir() and not child.name.startswith("_"):
                                out.add((region, sub.name, child.name))
        return sorted(out)

    for root in (LOCAL_ROOT, DRIVE_ROOT) if drive_online else (LOCAL_ROOT,):
        if not root.is_dir():
            continue
        for region_dir in root.iterdir():
            if not region_dir.is_dir() or region_dir.name.startswith("_"):
                continue
            for sub_dir in region_dir.iterdir():
                if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                    continue
                for c_dir in sub_dir.iterdir():
                    if c_dir.is_dir() and not c_dir.name.startswith("_"):
                        out.add((region_dir.name, sub_dir.name, c_dir.name))
    return sorted(out)


def storage_status(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    drive_online: bool | None = None,
    local_root: Path = LOCAL_ROOT,
    drive_root: Path = DRIVE_ROOT,
) -> list[dict]:
    if drive_online is None:
        drive_online = is_drive_online()

    rows: list[dict] = []
    for region_, subregion_, country_ in _enumerate_countries(
        region, subregion, country, drive_online
    ):
        local_dir = local_root / region_ / subregion_ / country_
        drive_dir = drive_root / region_ / subregion_ / country_
        l_rows, last_local = _country_news_stats(local_dir)
        if drive_online:
            d_rows, _ = _country_news_stats(drive_dir)
        else:
            d_rows = None
        if not local_dir.exists() and not drive_dir.exists():
            continue
        if not local_dir.exists() and not drive_online:
            continue
        rows.append(
            {
                "region": region_,
                "subregion": subregion_,
                "country": country_,
                "local_rows": l_rows if local_dir.exists() else None,
                "drive_rows": d_rows if drive_online and drive_dir.exists() else None,
                "last_local": last_local,
                "state": _country_state(local_dir, drive_dir, drive_online),
            }
        )
    return rows
