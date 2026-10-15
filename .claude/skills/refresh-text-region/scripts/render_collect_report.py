#!/usr/bin/env python3
"""Render a collect report from the runner's nohup log + jobs queue.

Reads:
  /tmp/refresh_<region>_nohup.log    — START/DONE/FAIL/BUDGET-HIT events
  /tmp/refresh_<region>_jobs.txt     — full queue (country|source per line)
  /tmp/refresh_<tag>.log             — per-source logs (for article counts)

Writes:
  outputs/text/reports/collect/collect_<region>_<ts>.md
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EVENT_RE = re.compile(
    r"\[(START|DONE|FAIL|STUCK|WARN|TIMEOUT|REFRESH-START|REFRESH-DONE|BUDGET-HIT)\s*\]"
    r"(?:\s+(?P<rest>.+?))?\s+@\s+(?P<ep>\d+)\s*$"
)
ARTICLES_RE = re.compile(r"Articles\s+Scraped:\s*(\d+)", re.IGNORECASE)


def fmt_dur(seconds: int | float | None) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 0:
        return "—"
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m{s % 60:02d}s"


def iso_time(epoch: int | None) -> str:
    if not epoch:
        return "—"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%H:%M:%S")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("region")
    ap.add_argument("--parallelism", type=int, required=True)
    ap.add_argument(
        "--max-source-seconds",
        type=int,
        required=True,
        help="per-source wall-clock cap that the runner was given",
    )
    args = ap.parse_args()

    region = args.region
    nohup = Path(f"/tmp/refresh_{region}_nohup.log")
    jobs_file = Path(f"/tmp/refresh_{region}_jobs.txt")

    if not nohup.exists():
        print(f"missing {nohup}", file=sys.stderr)
        return 1
    if not jobs_file.exists():
        print(f"missing {jobs_file}", file=sys.stderr)
        return 1

    refresh_start: int | None = None
    refresh_end: int | None = None
    budget_hit: int | None = None
    per_tag: dict[str, dict] = {}

    for raw in nohup.read_text(errors="replace").splitlines():
        m = EVENT_RE.search(raw)
        if not m:
            continue
        kind = m.group(1).strip()
        rest = (m.group("rest") or "").strip()
        ep = int(m.group("ep"))

        if kind == "REFRESH-START":
            refresh_start = ep
            continue
        if kind == "REFRESH-DONE":
            refresh_end = ep
            continue
        if kind == "BUDGET-HIT":
            budget_hit = ep
            continue

        tag = rest.split()[0] if rest else ""
        if not tag:
            continue
        rec = per_tag.setdefault(tag, {})
        if kind == "START":
            rec["start"] = ep
        elif kind == "TIMEOUT":
            rec["end"] = ep
            rec["status"] = "TIMEOUT-KILLED"
            rec["extra"] = "wall-clock cap"
            rec["timeout"] = True
        elif kind in ("DONE", "FAIL"):
            if rec.get("timeout"):
                continue
            rec["end"] = ep
            rec["status"] = kind
            extra = rest[len(tag) :].strip()
            if extra:
                rec["extra"] = extra

    job_tags: list[tuple[str, str, str]] = []
    for line in jobs_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        country, source = line.split("|", 1)
        tag = f"{country}__{source}" if source else country
        job_tags.append((tag, country, source))

    rows: list[dict] = []
    for tag, country, source in job_tags:
        rec = per_tag.get(tag, {})
        articles = "—"
        log_path = Path(f"/tmp/refresh_{tag}.log")
        if log_path.exists():
            try:
                for line in log_path.read_text(errors="replace").splitlines():
                    m = ARTICLES_RE.search(line)
                    if m:
                        articles = m.group(1)
                        break
            except Exception:
                pass

        if "start" not in rec:
            status = "NOT-STARTED"
            duration_s: int | None = None
            started = "—"
            notes = ""
        elif "status" not in rec:
            status = "IN-FLIGHT"
            cutoff = refresh_end or rec["start"]
            duration_s = max(0, cutoff - rec["start"])
            started = iso_time(rec["start"])
            notes = "still running when report rendered"
        else:
            status = rec["status"]
            duration_s = max(0, rec["end"] - rec["start"])
            started = iso_time(rec["start"])
            notes = rec.get("extra", "")

        rows.append(
            {
                "country": country,
                "source": source or "(all)",
                "status": status,
                "articles": articles,
                "duration_s": duration_s,
                "duration": fmt_dur(duration_s),
                "started": started,
                "notes": notes,
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    wall_s: int | None = None
    if refresh_start:
        end = refresh_end or budget_hit
        if end:
            wall_s = end - refresh_start
        else:
            # report rendered while still running — use latest known event epoch
            latest = max(
                (rec.get("end") or rec.get("start") or 0 for rec in per_tag.values()),
                default=0,
            )
            if latest:
                wall_s = latest - refresh_start

    done_with_durs = [
        r for r in rows if r["status"] == "DONE" and r["duration_s"] is not None
    ]
    done_with_durs.sort(key=lambda r: r["duration_s"])

    lines: list[str] = []
    lines.append(f"# Collect report — {region}")
    lines.append("")
    lines.append(
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_"
    )
    lines.append("")
    completed = counts.get("DONE", 0)
    lines.append(
        f"**Run:** region={region} | parallelism={args.parallelism} | "
        f"max_source={args.max_source_seconds}s | wall={fmt_dur(wall_s)} | "
        f"jobs={completed}/{len(rows)} completed"
    )
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append(
        "| Country | Source | Status | Articles | Duration | Started (UTC) | Notes |"
    )
    lines.append(
        "|---------|--------|--------|----------|----------|---------------|-------|"
    )
    for row in sorted(rows, key=lambda r: (r["country"], r["source"])):
        lines.append(
            f"| {row['country']} | {row['source']} | {row['status']} | "
            f"{row['articles']} | {row['duration']} | {row['started']} | {row['notes']} |"
        )

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary_parts = [f"{k}: {v}" for k, v in sorted(counts.items()) if v]
    lines.append(f"- {' | '.join(summary_parts)} | wall: {fmt_dur(wall_s)}")
    if done_with_durs:
        fastest = done_with_durs[0]
        slowest = done_with_durs[-1]
        lines.append(
            f"- Slowest: {slowest['country']}/{slowest['source']} ({slowest['duration']})"
        )
        lines.append(
            f"- Fastest: {fastest['country']}/{fastest['source']} ({fastest['duration']})"
        )
    lines.append("")

    out_dir = Path("outputs/text/reports/collect")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = refresh_start or 0
    ts = (
        datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if stamp
        else "noepoch"
    )
    out_path = out_dir / f"collect_{region}_{ts}.md"
    out_path.write_text("\n".join(lines))
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
