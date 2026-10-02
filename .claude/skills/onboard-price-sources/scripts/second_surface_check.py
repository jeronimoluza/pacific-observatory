#!/usr/bin/env python3
"""Phase 1 step 6 — does a domain you already cover serve a *second* surface?

Coverage is per surface, not per domain. Phase 2 subtracts the already-covered
set, which drops the whole domain from the candidate pool before anything is
probed. A tenant in the corpus can serve a second priced surface under a
different `analytical_role` and different COICOP codes, and nothing else in the
run will ever look at it.

`bluesky_prepaid_as.yaml` covered `bluesky.as` at `/personal/prepaid/plans/`
(`analytical_role: tariff`, `coicop_codes: ["08.1.0"]`). The same host served an
open WooCommerce Store API with 97 devices in USD at 08.2/08.3 and 09. Two
American Samoa discovery passes missed it.

Read every hit against the manifest's existing role. A hit on a domain already
filed `retailer_sku` is almost always that same catalog re-finding itself; a hit
on one filed `tariff`, `official_avg` or `cpi_benchmark` is a real second
surface, because those roles never describe a product catalog. Over American
Samoa's 19 covered domains this printed three hits and one signal.

    ssh a8 '~/venv/bin/python scripts/second_surface_check.py \\
        --config-dir ~/po/src/prices/configs/eap/pacific_islands/american_samoa'
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

try:
    from curl_cffi import requests as rq
except ImportError:
    print("curl_cffi missing — run this on a8 with ~/venv/bin/python", file=sys.stderr)
    raise SystemExit(2)

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
PROBES = [
    ("woocommerce", "/wp-json/wc/store/v1/products?per_page=1", None),
    ("shopify", "/products.json?limit=1", None),
    ("magento", "/graphql", MAGENTO_GQL),
    ("nopcommerce", "/api/products", None),
]

# Roles that never describe a product catalog. A platform hit on one of these is
# the interesting case.
NON_CATALOG_ROLES = {"tariff", "official_avg", "cpi_benchmark", "aggregate_proxy"}


def catalog_items(resp) -> int:
    """Items behind the endpoint, or 0 when this is not really a catalog."""
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


def scan_configs(config_dir: str) -> dict[str, dict]:
    """host -> {configs, roles} from every manifest in the directory."""
    found: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(config_dir, "*.yaml"))):
        txt = open(path, encoding="utf-8", errors="replace").read()
        roles = set(re.findall(r"^analytical_role:\s*(\S+)", txt, re.M))
        for url in re.findall(r'https?://[^\s"\'\)]+', txt):
            host = urlparse(url).netloc.lower()
            if not host:
                continue
            rec = found.setdefault(host, {"configs": set(), "roles": set()})
            rec["configs"].add(os.path.basename(path))
            rec["roles"] |= roles
    return found


def check(host: str) -> tuple[str, list]:
    hits = []
    for name, path, payload in PROBES:
        url = "https://%s%s" % (host, path)
        try:
            if payload is None:
                resp = rq.get(url, impersonate="chrome124", timeout=20)
            else:
                resp = rq.post(url, json=payload, impersonate="chrome124", timeout=20)
        except Exception:
            continue
        n = catalog_items(resp)
        if n:
            hits.append((name, path, n))
    return host, hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--config-dir", required=True, help="a country's configs/ directory"
    )
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    covered = scan_configs(os.path.expanduser(args.config_dir))
    if not covered:
        print("no manifests with URLs found in %s" % args.config_dir)
        return 0

    print("covered domains: %d" % len(covered))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check, sorted(covered)))

    signal, noise = [], []
    for host, hits in results:
        if not hits:
            continue
        roles = covered[host]["roles"]
        (signal if roles & NON_CATALOG_ROLES else noise).append((host, hits, roles))

    print("\n--- SECOND SURFACE (covered role is not a catalog role) ---")
    for host, hits, roles in signal:
        for name, path, n in hits:
            print(
                "  %-28s %-12s %-42s %4d items  role=%s  [%s]"
                % (
                    host,
                    name,
                    path,
                    n,
                    ",".join(sorted(roles)) or "?",
                    ",".join(sorted(covered[host]["configs"])),
                )
            )
    if not signal:
        print("  none")

    print("\n--- same surface (already filed as a catalog) ---")
    for host, hits, roles in noise:
        print("  %-28s role=%s" % (host, ",".join(sorted(roles)) or "?"))
    if not noise:
        print("  none")

    quiet = [h for h, hits in results if not hits]
    print("\n--- no platform surface (%d) ---" % len(quiet))
    print("  " + ", ".join(quiet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
