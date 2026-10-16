"""Weekly Google News coverage-gap report: Google's week count per source vs ours.

Per source, one RSS query ``site:<domain> after:<start-1> before:<end+1>`` per
edition until one returns items dated in the week (UTC pubDate). Results are
cached per (domain, edition), so sources sharing a domain cost one query.

Flags, in order (gap_ratio and min_google default to 0.5 and 10 in the CLI):
- error / not_probed: the query failed, or the run stopped before this source;
- not_indexed: Google has 0 items in the week in every edition tried;
- no_ours: the ledger cannot give a week count for this source (see sources.py);
- gap: ours / google < gap_ratio and google >= min_google. Valid at the cap too,
  since 100 is a lower bound on Google's count;
- at_cap_100: Google returned its 100-item maximum, so the ratio overstates us;
- ok.
"""

from __future__ import annotations

import csv
import random
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from text.gnews_gap.client import Blocked, FormatChanged, GoogleClient, Item
from text.gnews_gap.sources import (
    DATED_MIN,
    REPO,
    LedgerReader,
    Source,
    editions,
    iso2_map,
    norm_url,
    week_count_by_url_date,
)

REPORTS = REPO / "outputs/text/reports/gnews_gap"
CAP = 100
SAMPLE_SOURCES = 5
COLUMNS = [
    "source", "country", "region", "edition", "google_week_count", "ours_week_count",
    "ratio", "flag", "domain", "google_raw", "google_off_host", "ours_method",
    "ours_dated_share", "ours_n_news", "ledger_updated", "note",
]  # fmt: skip


def _host_ok(item: Item, src: Source) -> bool:
    if not (
        item.source_host == src.domain or item.source_host.endswith("." + src.domain)
    ):
        return False
    rx = src.gnews.get("host_regex")
    return not rx or re.search(rx, item.source_host) is not None


def _previous(week_start: date) -> dict[tuple[str, str], dict]:
    """Rows of the newest earlier-week report, by (region, source)."""
    runs = sorted(
        p for p in REPORTS.glob("*/gap.csv") if p.parent.name[:10] < str(week_start)
    )
    if not runs:
        return {}
    with open(runs[-1], newline="") as f:
        return {(r["region"], r["source"]): r for r in csv.DictReader(f)}


def _ours(
    src: Source, ledger: LedgerReader, prev: dict, start: date, end: date
) -> dict:
    row = ledger.row(src)
    if row is None:
        return dict(ours_method="none", note="no ledger row")
    out = dict(ours_n_news=row["n_news"], ledger_updated=row["updated"], _row=row)
    n, share = week_count_by_url_date(row["news"], start, end)
    out["ours_dated_share"] = round(share, 2)
    notes = []
    if row["updated"][:10] < str(end + timedelta(days=1)):
        notes.append("ledger last updated before week end")
    p = prev.get((src.region, src.source))
    if share >= DATED_MIN:
        out.update(ours_week_count=n, ours_method="url_date")
    elif p and p.get("ours_n_news") and p["ledger_updated"] != row["updated"]:
        out.update(
            ours_week_count=row["n_news"] - int(p["ours_n_news"]),
            ours_method="ledger_delta",
        )
    else:
        out["ours_method"] = "none"
        notes.append("URLs undated and no earlier report to diff against")
    out["note"] = "; ".join(notes)
    return out


def _flag(r: dict, gap_ratio: float, min_google: int) -> str:
    g, o = r.get("google_week_count"), r.get("ours_week_count")
    if g is None:
        return r.get("flag") or "error"
    if g == 0:
        return "not_indexed"
    if o is None:
        return "no_ours"
    if r["ratio"] < gap_ratio and g >= min_google:
        return "gap"
    if r["google_raw"] >= CAP:
        return "at_cap_100"
    return "ok"


def _google(src, client, iso2, cache, start, end):
    query = f"site:{src.domain} after:{start - timedelta(days=1)} before:{end + timedelta(days=1)}"
    tries = editions(src, iso2)
    for hl, gl in tries:
        if (src.domain, hl, gl) not in cache:
            cache[(src.domain, hl, gl)] = client.search(query, hl, gl)
        items = cache[(src.domain, hl, gl)]
        week = [i for i in items if start <= i.pub.date() <= end]
        on_host = [i for i in week if _host_ok(i, src)]
        if on_host:
            break
    else:
        hl, gl = tries[0]  # report the edition the config asks for
    return dict(
        edition=f"{gl}:{hl}",
        google_raw=len(items),
        google_week_count=len(on_host),
        google_off_host=len(week) - len(on_host),
        _items=on_host,
    )


def run(
    srcs: list[Source],
    start: date,
    gap_ratio: float,
    min_google: int,
    sample: int = 0,
    client: GoogleClient | None = None,
) -> tuple[Path, int]:
    """Probe, compare, write gap.csv + summary.txt (+ sample.csv). Returns (dir, exit code)."""
    end = start + timedelta(days=6)
    t0 = time.monotonic()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPORTS / f"{start}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    client = client or GoogleClient()
    iso2, cache, ledger, prev = iso2_map(), {}, LedgerReader(), _previous(start)
    rows, stop = [], None
    for i, src in enumerate(srcs):
        r = dict(
            source=src.source, country=src.country, region=src.region, domain=src.domain
        )
        if stop is None:
            try:
                r |= _google(src, client, iso2, cache, start, end)
            except (Blocked, FormatChanged, KeyboardInterrupt) as e:
                stop = f"{type(e).__name__}: {e}"
            except requests.RequestException as e:
                r["note"] = f"{type(e).__name__}: {e}"[:200]
        if stop is not None:
            r["flag"] = "not_probed"
        else:
            r |= _ours(src, ledger, prev, start, end)
            g, o = r.get("google_week_count"), r.get("ours_week_count")
            r["ratio"] = round(o / g, 2) if g and o is not None else None
        r["flag"] = _flag(r, gap_ratio, min_google)
        rows.append(r)
        print(
            f"  [{i + 1}/{len(srcs)}] {src.region}/{src.country}/{src.source}: "
            f"google={r.get('google_week_count')} ours={r.get('ours_week_count')} {r['flag']}",
            flush=True,
        )
    samples = []
    if sample and stop is None:
        try:
            samples = _sample(rows, srcs, client, sample)
        except (Blocked, FormatChanged, KeyboardInterrupt) as e:
            stop = f"{type(e).__name__} during --sample: {e}"
    _write(
        out_dir,
        rows,
        samples,
        start,
        end,
        client,
        time.monotonic() - t0,
        stop,
        gap_ratio,
        min_google,
    )
    return out_dir, 1 if stop else 0


def _sample(rows, srcs, client, n) -> list[dict]:
    """Decode n Google items for each of the SAMPLE_SOURCES largest gaps."""
    by_name = {(s.region, s.source): s for s in srcs}
    gaps = sorted(
        (r for r in rows if r["flag"] == "gap"),
        key=lambda r: r["google_week_count"] - r["ours_week_count"],
        reverse=True,
    )[:SAMPLE_SOURCES]
    out = []
    for r in gaps:
        src = by_name[(r["region"], r["source"])]
        seen = r.get("_row", {}).get("seen", set())
        rx = src.gnews.get("path_regex")
        items = r["_items"]
        for item in random.Random(0).sample(items, min(n, len(items))):
            url = client.decode(item.link)
            path = url and (re.sub(r"^https?://[^/]+", "", url) or "/")
            out.append(dict(
                source=src.source, country=src.country, pub=item.pub.isoformat(),
                title=item.title, url=url or "", in_ours=bool(url) and norm_url(url) in seen,
                path_regex_match="" if not (rx and url) else bool(re.search(rx, path)),
            ))  # fmt: skip
            print(
                f"  sample {src.source}: {(url or 'DECODE FAILED')[:100]}", flush=True
            )
    return out


def _write(
    out_dir, rows, samples, start, end, client, secs, stop, gap_ratio, min_google
):
    with open(out_dir / "gap.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    if samples:
        with open(out_dir / "sample.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(samples[0]))
            w.writeheader()
            w.writerows(samples)
    flags: dict[str, int] = {}
    for r in rows:
        flags[r["flag"]] = flags.get(r["flag"], 0) + 1
    gaps = sorted(
        (r for r in rows if r["flag"] == "gap"),
        key=lambda r: r["google_week_count"] - r["ours_week_count"],
        reverse=True,
    )
    lines = [
        f"Google News coverage gap, week {start}..{end} (UTC pubDate)",
        f"run {out_dir.name}: {len(rows)} sources, {client.requests} Google requests, "
        f"{client.blocks} blocks, {secs / 60:.1f} min",
        f"gap = ours/google < {gap_ratio} and google >= {min_google}",
        "flags: " + ", ".join(f"{k}={v}" for k, v in sorted(flags.items())),
    ]
    if stop:
        lines.append(f"STOPPED EARLY (partial results): {stop}")
    if samples:
        hit = sum(s["in_ours"] for s in samples)
        dec = sum(bool(s["url"]) for s in samples)
        lines.append(
            f"sample: {dec}/{len(samples)} decoded, {hit} already in our ledger"
        )
        scoped = [s for s in samples if s["path_regex_match"] != ""]
        if scoped:
            m = sum(s["path_regex_match"] for s in scoped)
            lines.append(
                f"sample: {m}/{len(scoped)} match their source's gnews.path_regex"
            )
    lines.append("largest gaps (source country google ours ratio edition):")
    lines += [
        f"  {r['source']} {r['country']} {r['google_week_count']} {r['ours_week_count']} "
        f"{r['ratio']} {r['edition']}"
        for r in gaps[:15]
    ]
    (out_dir / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
