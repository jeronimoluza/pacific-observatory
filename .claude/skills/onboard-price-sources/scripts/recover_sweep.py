#!/usr/bin/env python3
"""Bulk re-probe of the recheck view. The `recover` route's engine.

Why this exists: a recovered host has *zero* discovery cost. The domain is
already known, already classified, already in an inventory. Re-probing 400
hosts costs about what re-probing 4 costs, because the agent reads a summary
rather than 400 responses. Recorded hit rates on this corpus: 16 of 26 in one
shard; 11 of 125 on a different TLS profile; a large share of 112 SKIP_WAF
verdicts on the single curl_cffi lever.

Sharded by blocker class on purpose. NXDOMAIN and dead hosts re-probe at full
speed and are pure profit. A hardened-CDN shard needs pacing or it re-confirms
blocks that are really just our own request volume from one IP — that is how
`handla.ica.se` failed three acceptance runs after probing clean in isolation.

Run it on a8. A backgrounded `&` over ssh dies with the connection and the
harness cannot see remote processes:

    ssh a8 'cd ~/po/.claude/skills/onboard-price-sources && \
      setsid nohup ~/venv/bin/python scripts/recover_sweep.py \
        --class unreachable-fast --run-id rec1 \
        > /tmp/rec1.log 2>&1 </dev/null &'
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE.parent / "references" / "probe_log"

RECHECK_DAYS = 180

# The ladder, in the order that pays. They are not interchangeable: mall.cz and
# allegro.cz clear only on safari17_0; seven hosts across Syria, Botswana and
# Liberia behind Hostinger `hcdn` clear only on firefox133; comfy.ua returns a
# 6 KB Imperva stub on all four Chrome/Safari profiles and an 888 KB real page
# on firefox133.
PROFILES = ["chrome124", "chrome120", "safari17_0", "firefox133"]

# Per-class pacing. The number is seconds of sleep between requests per worker.
CLASS_PACING = {
    "unreachable-fast": (16, 0.0),
    "blocked-unspecified": (8, 0.5),
    "cdn-edge": (6, 1.0),
    "no-catalog": (8, 0.5),
    "app-only": (8, 0.5),
    "needs-work": (6, 1.0),
    "out-of-scope": (8, 0.5),
    "waf-hardened-paced": (2, 4.0),
}
DEFAULT_PACING = (4, 1.0)

# A storefront is not proven by a 200. These are the endpoints that turn a 200
# into a candidate worth an agent's attention.
# Magento answers /rest/V1/store/storeConfigs with XML or 401 on every store we
# tried, so the REST probe silently excluded every Magento host from a 2,214-host
# sweep. GraphQL is the surface that actually answers anonymously.
MAGENTO_GQL = {
    "query": '{products(search:"a",pageSize:1){total_count items'
    "{name price_range{minimum_price{regular_price{value currency}}}}}}"
}

# (name, path, json payload). A payload means POST; None means GET.
# Ask for ONE item: existence needs one, and shopsampars.com's item 5 crashes
# its Store API (HTTP 500 after 45 s), so per_page=5 filed a live catalog
# as no_catalog.
PLATFORM_PROBES = [
    ("woocommerce", "/wp-json/wc/store/v1/products?per_page=1", None),
    ("shopify", "/products.json?limit=1", None),
    ("magento", "/graphql", MAGENTO_GQL),
    ("nopcommerce", "/api/products", None),
]


def catalog_items(resp) -> int:
    """Items behind a platform endpoint, or 0 if this is not really a catalog.

    A 200 is not a catalog. Half of one 400-host sweep's "open catalogs" were
    SPA shells: sites route every unknown path to index.html and answer the
    WooCommerce probe with 3 KB of HTML. Require JSON, require it to parse,
    require a non-empty item list.
    """
    if resp.status_code != 200:
        return 0
    if "json" not in resp.headers.get("content-type", "").lower():
        return 0
    try:
        data = resp.json()
    except Exception:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        # Magento GraphQL nests the catalog as data.products.items.
        inner = data.get("data")
        if isinstance(inner, dict):
            node = inner.get("products")
            if isinstance(node, dict) and isinstance(node.get("items"), list):
                return len(node["items"])
        for key in ("products", "items", "data"):
            if isinstance(data.get(key), list):
                return len(data[key])
    return 0


def load_queue(klass: str | None, limit: int) -> list[dict]:
    cmd = [sys.executable, str(HERE / "probe_log.py"), "recheck", "--limit", str(limit)]
    if klass:
        cmd += ["--class", klass]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            rows.append({"host": parts[0], "was": parts[1], "lever": parts[2]})
    return rows


def probe(host: str, pause: float) -> dict:
    """Walk the TLS ladder, stop at the first 200, then fingerprint."""
    try:
        from curl_cffi import requests as rq
    except ImportError:
        return {"host": host, "verdict": "error", "tell": "curl_cffi not installed"}

    result = {
        "host": host,
        "verdict": "blocked",
        "lever_tried": None,
        "tell": None,
        "platform": None,
        "url_shape": None,
        "items": None,
        "bytes": 0,
    }
    tried = []
    for prof in PROFILES:
        tried.append(prof)
        try:
            r = rq.get(f"https://{host}/", impersonate=prof, timeout=25)
        except Exception as exc:  # DNS, TLS, reset — all real verdicts
            msg = type(exc).__name__
            result["tell"] = msg
            # curl says "Could not resolve host"; the class is DNSError. Matching
            # "Resolve" missed both and filed 45 dead Jamaica domains as blocked.
            if msg == "DNSError" or "resolve" in str(exc).lower():
                result["verdict"] = "unreachable"
                result["lever_tried"] = f"curl_cffi:{','.join(tried)}"
                return result
            time.sleep(pause)
            continue
        result["bytes"] = len(r.text or "")
        if r.status_code == 200 and result["bytes"] > 2000:
            result["verdict"] = "ok"
            result["lever_tried"] = f"curl_cffi:{prof}"
            result["tell"] = f"http-200 {result['bytes']}B"
            # A 200 is access, not enumerability. Fingerprint so the agent
            # knows whether there is a catalog behind it before it spends a
            # probe budget on the host.
            for name, path, payload in PLATFORM_PROBES:
                url = f"https://{host}{path}"
                try:
                    if payload is None:
                        p = rq.get(url, impersonate=prof, timeout=20)
                    else:
                        p = rq.post(url, json=payload, impersonate=prof, timeout=20)
                except Exception:
                    continue
                n = catalog_items(p)
                if n:
                    result["platform"] = name
                    result["url_shape"] = path
                    result["items"] = n
                    break
            return result
        result["tell"] = f"http-{r.status_code}"
        time.sleep(pause)
    result["lever_tried"] = f"curl_cffi:{','.join(tried)}"
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="klass", help="sweep class to re-probe")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument(
        "--dry-run", action="store_true", help="probe but do not append to the log"
    )
    args = ap.parse_args()

    workers, pause = CLASS_PACING.get(args.klass or "", DEFAULT_PACING)
    queue = load_queue(args.klass, args.limit)
    if not queue:
        print("recheck queue empty for that class")
        return 0

    print(
        f"class={args.klass or 'all'} hosts={len(queue)} workers={workers} pause={pause}s"
    )
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda r: probe(r["host"], pause), queue))

    counts = Counter(r["verdict"] for r in results)
    recovered = [r for r in results if r["verdict"] == "ok"]
    with_catalog = [r for r in recovered if r["platform"]]

    print(f"\nelapsed {time.time() - t0:.0f}s")
    for v, n in counts.most_common():
        print(f"  {v:<14} {n}")
    print(
        f"\nrecovered           {len(recovered)} / {len(queue)} ({len(recovered)/len(queue):.0%})"
    )
    print(f"  with open catalog {len(with_catalog)}")
    for r in with_catalog[:40]:
        print(f"    {r['host']:<38} {r['platform']:<14} {r['url_shape']}")

    if args.dry_run:
        print("\n(dry run — nothing appended)")
        return 0

    LOG_DIR.mkdir(exist_ok=True)
    shard = LOG_DIR / f"{args.run_id}-recover-{args.klass or 'all'}.jsonl"
    today = date.today().isoformat()
    # A re-confirmed block is still only a verdict with a decay rate.
    next_check = (date.today() + timedelta(days=RECHECK_DAYS)).isoformat()
    with shard.open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(
                json.dumps(
                    {
                        "host": r["host"],
                        "probed_at": today,
                        "discovery_method": "recover_sweep",
                        "discovery_detail": args.klass,
                        "platform": r["platform"],
                        "url_shape": r["url_shape"],
                        "items": r.get("items"),
                        "verdict": r["verdict"],
                        "lever_tried": r["lever_tried"],
                        "tell": r["tell"],
                        "shipped": False,
                        "recheck_after": None if r["verdict"] == "ok" else next_check,
                        "source": f"run:{args.run_id}",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"\nappended {len(results)} rows -> {shard.name}")
    print(
        f"cost: files_read=0 bytes_read=0 probes_run={len(results)} "
        f"agents_spawned=0 sources_shipped=0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
