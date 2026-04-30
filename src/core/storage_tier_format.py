"""Output formatters for `po text {archive,restore,storage-status}` results.

Split from `storage_tier.py` to keep both files under the 500-line cap.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from core.storage_tier import DRIVE_ROOT, LOCAL_ROOT


def _fmt_int(n: int | None) -> str:
    if n is None:
        return "—"
    return f"{n:,}"


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(n)
    for u in units:
        if val < 1024 or u == units[-1]:
            return f"{val:.1f} {u}"
        val /= 1024
    return f"{val:.1f} TB"


def format_status_table(rows: list[dict], drive_online: bool) -> str:
    if not rows:
        return "  (no data found for requested scope)"
    header = (
        f"  {'REGION':<8}{'SUBREGION':<18}{'COUNTRY':<22}"
        f"{'LOCAL_ROWS':>12}{'DRIVE_ROWS':>12}  {'LAST_LOCAL':<12}{'STATE':<14}"
    )
    sep = "  " + "─" * (len(header) - 2)
    lines = [header, sep]
    for r in rows:
        drive_disp = "(offline)" if not drive_online else _fmt_int(r["drive_rows"])
        lines.append(
            f"  {r['region']:<8}{r['subregion']:<18}{r['country']:<22}"
            f"{_fmt_int(r['local_rows']):>12}{drive_disp:>12}  "
            f"{(r['last_local'] or '—'):<12}{r['state']:<14}"
        )
    if not drive_online:
        lines.append("")
        lines.append("  (drive offline — drive columns blank, state suffixed with ?)")
    return "\n".join(lines)


def format_status_json(rows: list[dict], drive_online: bool) -> str:
    payload = {
        "drive_online": drive_online,
        "drive_root": str(DRIVE_ROOT),
        "local_root": str(LOCAL_ROOT),
        "computed_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": rows,
    }
    return json.dumps(payload, indent=2)


def format_archive_summary(
    result: dict,
    pairs: list[tuple[Path, Path]],
    scope_label: str,
) -> str:
    out: list[str] = []
    if not result["ok"]:
        out.append(
            f"  ✗ Archive verification FAILED for {scope_label}: "
            f"{len(result['mismatches'])} mismatches"
        )
        for m in result["mismatches"][:20]:
            out.append(f"    - {m}")
        if len(result["mismatches"]) > 20:
            out.append(f"    … and {len(result['mismatches']) - 20} more")
        out.append("  No rm hint — local data is NOT safe to delete.")
        return "\n".join(out)

    out.append(
        f"  ✓ Archived {scope_label} — {result['files']} files, "
        f"{_fmt_bytes(result['bytes'])}, "
        f"{result['news_files_verified']} news.csv verified."
    )
    if result.get("news_only"):
        out.append("  (news-only mode — non-news files on drive untouched)")
    out.append("")
    out.append("  To free local space, run:")
    rm_targets = " ".join(str(p[0]) for p in result["verified_pairs"])
    out.append(f"    rm -rf {rm_targets}")
    return "\n".join(out)


def format_restore_summary(
    result: dict,
    pairs: list[tuple[Path, Path]],
    scope_label: str,
) -> str:
    out: list[str] = []
    if not result["ok"]:
        out.append(
            f"  ✗ Restore verification FAILED for {scope_label}: "
            f"{len(result['mismatches'])} mismatches"
        )
        for m in result["mismatches"][:20]:
            out.append(f"    - {m}")
        return "\n".join(out)

    out.append(
        f"  ✓ Restored {scope_label} — {result['files']} files, "
        f"{_fmt_bytes(result['bytes'])}, "
        f"{result['news_files_verified']} news.csv verified."
    )
    if result["local_newer"]:
        out.append("")
        out.append("  ⚠ Local has data the drive doesn't — re-archive before pruning:")
        for m in result["local_newer"][:20]:
            out.append(f"    - {m}")
        if len(result["local_newer"]) > 20:
            out.append(f"    … and {len(result['local_newer']) - 20} more")
    return "\n".join(out)


def describe_scope(
    region: str | None,
    subregion: str | None,
    country: str | None,
    source: str | None,
    path: str | None,
) -> str:
    if path:
        return f"path:{path}"
    parts = []
    if region:
        parts.append(f"region={region}")
    if subregion:
        parts.append(f"subregion={subregion}")
    if country:
        parts.append(f"country={country}")
    if source:
        parts.append(f"source={source}")
    return ", ".join(parts) if parts else "(none)"
