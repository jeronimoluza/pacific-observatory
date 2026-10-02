#!/usr/bin/env python3
"""The probe log: one row per candidate probed, shipped or not.

Blockers are not a separate store. They are the view `verdict != ok`. The
recheck queue is the view `lever_tried is null OR recheck_after <= today`.

Workers append to their own shard (`<run_id>-<country>.jsonl`); the
orchestrator commits the directory. Shards are new files, so parallel waves
never conflict in git, and a bad shard is deletable without rewriting history.
Nothing is ever compacted: a host reading `blocked` in July and `ok` in
September is the evidence that the recover route works.

    # record a probe (refuses a block verdict with no lever named)
    python probe_log.py append --run-id w7 --country american_samoa \
        --host example.as --verdict blocked --lever curl_cffi:chrome124,firefox133 \
        --tell http-403 --discovery-method ddgs --discovery-detail "supermarket american samoa"

    # what should be re-probed
    python probe_log.py recheck --limit 50 --class waf-hardened-paced

    # has anyone looked at this host before?
    python probe_log.py lookup example.as

    # how did the ordering do? (self-audit for the fingerprint-first gate)
    python probe_log.py audit
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE.parent / "references" / "probe_log"

RECHECK_DAYS = 180

FIELDS = [
    "host",
    "probed_at",
    "discovery_method",
    "discovery_detail",
    "platform",
    "url_shape",
    "verdict",
    "lever_tried",
    "tell",
    "shipped",
    "recheck_after",
]

VERDICTS = (
    "ok",
    "blocked",
    "no_catalog",
    "app_only",
    "out_of_scope",
    "unreachable",
    "needs_work",
)

# A verdict that forecloses a host must name what was tried. Without it the row
# is indistinguishable from "nobody looked", which is how 112 bare-curl 403s
# became permanent skips.
LEVER_REQUIRED = {"blocked", "unreachable"}


def read_all() -> list[dict]:
    rows = []
    if not LOG_DIR.exists():
        return rows
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                print(f"skipping malformed line in {path.name}", file=sys.stderr)
                continue
            r.setdefault("_shard", path.stem)
            rows.append(r)
    return rows


def latest_per_host(rows: list[dict]) -> dict[str, dict]:
    """Most recent row per host. Undated rows lose to dated ones."""
    best: dict[str, dict] = {}
    for r in rows:
        h = r["host"]
        cur = best.get(h)
        if cur is None:
            best[h] = r
            continue
        if (r.get("probed_at") or "") > (cur.get("probed_at") or ""):
            best[h] = r
    return best


def cmd_append(args: argparse.Namespace) -> int:
    if args.verdict in LEVER_REQUIRED and not args.lever:
        print(
            f"refused: verdict '{args.verdict}' needs --lever naming what was tried.\n"
            f"A bare-curl 403 is not a lever. Run the curl_cffi profile ladder "
            f"(chrome124, chrome120, safari17_0, firefox133) first.",
            file=sys.stderr,
        )
        return 2

    probed_at = args.probed_at or date.today().isoformat()
    recheck = None
    if args.verdict != "ok":
        d = datetime.strptime(probed_at, "%Y-%m-%d").date()
        recheck = (d + timedelta(days=RECHECK_DAYS)).isoformat()

    rec = {
        "host": args.host.lower().removeprefix("www."),
        "probed_at": probed_at,
        "discovery_method": args.discovery_method,
        "discovery_detail": args.discovery_detail,
        "platform": args.platform,
        "url_shape": args.url_shape,
        "verdict": args.verdict,
        "lever_tried": args.lever,
        "tell": args.tell,
        "shipped": args.shipped,
        "recheck_after": recheck,
        "rank_predicted": args.rank_predicted,
        "source": f"run:{args.run_id}",
    }

    LOG_DIR.mkdir(exist_ok=True)
    shard = LOG_DIR / f"{args.run_id}-{args.country}.jsonl"
    with shard.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"appended {rec['host']} -> {shard.name}")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    rows = [
        r
        for r in read_all()
        if r["host"] == args.host.lower().removeprefix("www.")
        or r["host"].endswith("." + args.host.lower())
    ]
    if not rows:
        print("no prior probe recorded")
        return 0
    rows.sort(key=lambda r: r.get("probed_at") or "")
    for r in rows:
        print(
            f"{r.get('probed_at') or '(undated)':<12} {r['verdict']:<12} "
            f"lever={r.get('lever_tried') or '-'} tell={r.get('tell') or '-'} "
            f"shard={r.get('_shard')}"
        )
    if len(rows) > 1 and rows[0]["verdict"] != rows[-1]["verdict"]:
        print("\nverdict changed over time — trust the most recent row.")
    return 0


def cmd_recheck(args: argparse.Namespace) -> int:
    today = date.today().isoformat()
    latest = latest_per_host(read_all())
    queue = []
    for r in latest.values():
        if r["verdict"] == "ok":
            continue
        if r.get("shipped"):
            continue
        no_lever = not r.get("lever_tried")
        expired = (r.get("recheck_after") or "9999") <= today
        if no_lever or expired:
            if (
                args.klass
                and r.get("_shard", "").replace("migration-", "") != args.klass
            ):
                continue
            queue.append(r)
    # Cheapest first: a host with no lever recorded has never really been tested.
    queue.sort(key=lambda r: (bool(r.get("lever_tried")), r.get("probed_at") or ""))

    if args.count:
        print(len(queue))
        return 0
    for r in queue[: args.limit]:
        print(
            f"{r['host']}\t{r['verdict']}\t{r.get('lever_tried') or 'NO-LEVER'}"
            f"\t{r.get('probed_at') or '-'}\t{r.get('_shard')}"
        )
    print(
        f"\n-- {len(queue)} in queue, showing {min(args.limit, len(queue))}",
        file=sys.stderr,
    )
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    rows = read_all()
    latest = latest_per_host(rows)
    print(f"rows          {len(rows)}")
    print(f"hosts         {len(latest)}")
    print(f"shards        {len(list(LOG_DIR.glob('*.jsonl')))}")
    print("\nlatest verdict per host:")
    for v, n in Counter(r["verdict"] for r in latest.values()).most_common():
        print(f"  {v:<16} {n}")
    print("\nevidence:")
    for f in ("lever_tried", "tell", "probed_at", "platform", "discovery_method"):
        n = sum(1 for r in latest.values() if r.get(f))
        print(f"  {f:<18} {n:>5} / {len(latest)}")
    flips = 0
    by_host = defaultdict(list)
    for r in rows:
        by_host[r["host"]].append(r)
    for h, rs in by_host.items():
        if len({x["verdict"] for x in rs}) > 1:
            flips += 1
    print(f"\nhosts whose verdict changed over time: {flips}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Did the fingerprint-first ordering predict anything?

    Ships provisional and self-auditing: the gate is falsifiable only once a few
    hundred probes carry rank_predicted. Until then this prints how far off it is.
    """
    rows = [r for r in read_all() if r.get("rank_predicted") is not None]
    if not rows:
        print(
            "no ranked probes logged yet — the ordering is unaudited.\n"
            "It orders and budgets; it never filters, so this is not a blocker."
        )
        return 0
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        b = buckets[r["rank_predicted"]]
        b[0] += 1
        b[1] += int(r["verdict"] == "ok" or bool(r.get("shipped")))
    print("rank  probed  passed  rate")
    for rank in sorted(buckets):
        n, ok = buckets[rank]
        print(f"{rank:<6}{n:<8}{ok:<8}{ok / n:.0%}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("append")
    a.add_argument("--run-id", required=True)
    a.add_argument("--country", required=True)
    a.add_argument("--host", required=True)
    a.add_argument("--verdict", required=True, choices=VERDICTS)
    a.add_argument(
        "--lever", help="what was actually tried, e.g. curl_cffi:chrome124,firefox133"
    )
    a.add_argument(
        "--tell", help="the signature you saw, e.g. cf-mitigated or http-403"
    )
    a.add_argument("--platform")
    a.add_argument("--url-shape", help="e.g. /wp-json/wc/store/v1/products")
    a.add_argument(
        "--discovery-method",
        choices=[
            "inventory",
            "marketplace_directory",
            "ddgs",
            "handover_list",
            "platform_fingerprint",
            "recover_sweep",
            "user_supplied",
        ],
    )
    a.add_argument("--discovery-detail", help="the query or directory that produced it")
    a.add_argument(
        "--rank-predicted", type=int, help="rank the ordering gave it before probing"
    )
    a.add_argument("--shipped", action="store_true")
    a.add_argument("--probed-at")
    a.set_defaults(func=cmd_append)

    r = sub.add_parser("recheck")
    r.add_argument("--limit", type=int, default=50)
    r.add_argument("--class", dest="klass", help="restrict to one sweep class")
    r.add_argument("--count", action="store_true")
    r.set_defaults(func=cmd_recheck)

    lo = sub.add_parser("lookup")
    lo.add_argument("host")
    lo.set_defaults(func=cmd_lookup)

    sub.add_parser("stats").set_defaults(func=cmd_stats)
    sub.add_parser("audit").set_defaults(func=cmd_audit)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
