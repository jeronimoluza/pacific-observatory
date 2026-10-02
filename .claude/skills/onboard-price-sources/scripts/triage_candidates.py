#!/usr/bin/env python3
"""Phase 2 triage — probe every candidate, show the agent only what needs a judgement.

Discovery cost is the agent reading candidates one at a time, not the probing.
On the Jamaica blind A/B (2026-09-17, audited 2026-09-25) an agent-led arm paid
19,907 tokens per accepted source; a script-first arm paid 4,690 — and 19 of the
script arm's 27 false positives failed a check a script can make without reading
a page: prices in another currency, every price zero, or fewer than 10 items.

This runs the whole pipeline on a candidate file:

  1. drop noise hosts, de-duplicate
  2. `curl_cffi` profile ladder + platform probes (recover_sweep.probe)
  3. open platform catalog -> sample 10 items: count, currency, prices
  4. no platform catalog  -> HTML fallback (html_catalog_check.check)
  5. tier every host:
       accept      catalog in the local currency, priced, >= 10 items
       adjudicate  catalog in another currency, or priced HTML without proof
                   of enumeration — the ONLY rows the agent reads
       reject      too_small / zero_prices / no_catalog / blocked / unreachable

Every host lands in the probe log with its verdict and a rank_predicted, so the
ordering gate's audit gets data and nothing is silently dropped.

    # on a8, from the skill directory
    ~/venv/bin/python scripts/triage_candidates.py --from-sweep sweep.jsonl \\
        --currency FJD --symbol 'FJ$' --run-id fj1 --country fiji --out triage.jsonl
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import html_catalog_check as hcc
import recover_sweep as rs

try:
    from curl_cffi import requests as rq
except ImportError:
    print("curl_cffi missing — run this on a8 with ~/venv/bin/python", file=sys.stderr)
    raise SystemExit(2)

LOG_DIR = Path(__file__).resolve().parent.parent / "references" / "probe_log"
MIN_ITEMS = 10

# Currencies a country shares with a big foreign market. There a currency match
# proves nothing — a US store prices in USD too — so a match goes to adjudicate
# and the agent checks ccTLD and shipping policy (discover.md, Phase 2.5 trap).
SHARED_CURRENCIES = {"USD", "EUR", "GBP", "AUD", "NZD"}

# ddgs_search.md "Filter the noise before probing", plus the global giants a
# country query pack drags in. Matched as a suffix of the host.
NOISE = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "pinterest.com",
    "reddit.com",
    "wikipedia.org",
    "apps.apple.com",
    "play.google.com",
    "sites.google.com",
    "statista.com",
    "tripadvisor.com",
    "hikersbay.com",
    "selinawamucii.com",
    "academia.edu",
    "scribd.com",
    "studocu.com",
    "numbeo.com",
    "livingcost.org",
    "expatistan.com",
    "mylifeelsewhere.com",
    "nomadlist.com",
    "ubuy.com",
    "desertcart.com",
    "parceldaddy.com",
    "amazon.com",
    "ebay.com",
    "temu.com",
    "aliexpress.com",
    "yelp.com",
)

GQL = {
    "query": '{products(search:"a",pageSize:10){total_count items{name price_range'
    "{minimum_price{regular_price{value currency}}}}}}"
}


def fetch(method, url, prof="chrome124", **kw):
    try:
        return getattr(rq, method)(url, impersonate=prof, timeout=30, **kw)
    except Exception:
        return None


def as_json(resp):
    if resp is None or resp.status_code != 200:
        return None
    if "json" not in resp.headers.get("content-type", "").lower():
        return None
    try:
        return resp.json()
    except Exception:
        return None


def sample_woo(host, prof):
    base = "https://%s/wp-json/wc/store/v1/products" % host
    r = fetch("get", base + "?per_page=10", prof)
    data = as_json(r)
    total = r.headers.get("x-wp-total") if data is not None else None
    small = None
    if isinstance(data, list):
        small = int(total) < MIN_ITEMS if total else len(data) < MIN_ITEMS
    else:
        # One bad product can 500 the whole page (shopsampars.com, item 5).
        data = []
        for page in (1, 2, 3):
            r = fetch("get", base + "?per_page=1&page=%d" % page, prof)
            got = as_json(r)
            if isinstance(got, list):
                data += got
                total = total or r.headers.get("x-wp-total")
        if total:
            small = int(total) < MIN_ITEMS
    items = []
    for p in data:
        pr = p.get("prices") or {}
        try:
            val = int(pr.get("price") or 0) / 10 ** int(
                pr.get("currency_minor_unit") or 0
            )
        except ValueError:
            val = None
        items.append(
            (htmllib.unescape(p.get("name", "")), val, pr.get("currency_code"))
        )
    return {"count": int(total) if total else None, "small": small, "items": items}


def sample_shopify(host, prof):
    data = as_json(
        fetch("get", "https://%s/products.json?limit=%d" % (host, MIN_ITEMS), prof)
    )
    products = data.get("products", []) if isinstance(data, dict) else []
    # cart.js is JSON served as application/javascript, so as_json() refuses it.
    cur = None
    r = fetch("get", "https://%s/cart.js" % host, prof)
    if r is not None and r.status_code == 200:
        try:
            cur = r.json().get("currency")
        except Exception:
            pass
    items = []
    for p in products:
        v = (p.get("variants") or [{}])[0]
        try:
            val = float(v.get("price"))
        except (TypeError, ValueError):
            val = None
        items.append((p.get("title", ""), val, cur))
    small = len(products) < MIN_ITEMS if data is not None else None
    return {
        "count": None if not small else len(products),
        "small": small,
        "items": items,
    }


def sample_magento(host, prof):
    data = as_json(fetch("post", "https://%s/graphql" % host, prof, json=GQL))
    try:
        node = data["data"]["products"]
    except (TypeError, KeyError):
        return {"count": None, "small": None, "items": []}
    items = []
    for p in node.get("items") or []:
        rp = p["price_range"]["minimum_price"]["regular_price"]
        items.append((p["name"], rp.get("value"), rp.get("currency")))
    total = node.get("total_count")
    return {
        "count": total,
        "small": total < MIN_ITEMS if total is not None else None,
        "items": items,
    }


SAMPLERS = {
    "woocommerce": sample_woo,
    "shopify": sample_shopify,
    "magento": sample_magento,
}


def title_of(host):
    r = fetch("get", "https://%s/" % host)
    m = re.search(
        r"<title[^>]*>([^<]{0,80})", (r.text or "") if r is not None else "", re.I
    )
    return htmllib.unescape(m.group(1)).strip() if m else None


def triage(cand, code, local):
    host = cand["host"]
    probe = rs.probe(host, 0.5)
    if probe["verdict"] == "unreachable":
        # load() strips www., and statsfiji.gov.fj only resolves with it.
        www = rs.probe("www." + host, 0.5)
        if www["verdict"] != "unreachable":
            host, probe = "www." + host, www
    row = {
        **cand,
        "host": host,
        "platform": probe.get("platform"),
        "url_shape": probe.get("url_shape"),
        "lever_tried": probe.get("lever_tried"),
        "tell": probe.get("tell"),
        "tier": "reject",
        "reason": None,
        "rank": 5,
        "count": None,
        "currency": None,
        "items": [],
    }

    if probe["verdict"] in ("unreachable", "blocked"):
        row.update(verdict=probe["verdict"], reason=probe["verdict"])
        return row

    if row["platform"] in SAMPLERS:
        # Sample with the profile that cleared the probe: farmboyfiji.com
        # serves JSON to safari17_0 and a SiteGround captcha to chrome124.
        prof = (probe.get("lever_tried") or "").split(":")[-1] or "chrome124"
        s = SAMPLERS[row["platform"]](host, prof)
        if not s["items"]:
            row.update(verdict="blocked", reason="blocked", tell="sample challenged")
            return row
        curs = Counter(c for _, _, c in s["items"] if c)
        row.update(
            count=s["count"],
            items=s["items"][:5],
            currency=curs.most_common(1)[0][0] if curs else None,
        )
        prices = [v for _, v, _ in s["items"] if v is not None]
        if s["small"]:
            row.update(
                verdict="no_catalog",
                reason="too_small",
                rank=4,
                tell="%s items" % s["count"],
            )
        elif prices and sum(1 for v in prices if not v) > len(prices) / 2:
            # gcaja.com: 919 products, 9 of 10 sampled at 0.0 — a quote-only
            # distributor. "Every price zero" let it through on the tenth.
            row.update(
                verdict="no_catalog",
                reason="zero_prices",
                rank=4,
                tell="%d of %d sampled prices are 0"
                % (sum(1 for v in prices if not v), len(prices)),
            )
        elif row["currency"] and row["currency"] != code:
            # Diaspora and export shops: Jamaican goods priced for foreigners.
            # All 9 in the Jamaica audit priced in USD or CAD.
            row.update(
                verdict="out_of_scope",
                reason="foreign_currency",
                rank=4,
                tell="prices in %s, not %s" % (row["currency"], code),
            )
        elif row["currency"] == code and code not in SHARED_CURRENCIES:
            row.update(
                tier="accept",
                verdict="ok",
                rank=1,
                tell="json-catalog %s, %s" % (s["count"] or ">=10", code),
            )
        else:
            row.update(
                tier="adjudicate",
                verdict="needs_work",
                rank=2,
                reason="currency %s%s"
                % (
                    row["currency"] or "unknown",
                    " (shared)" if row["currency"] else "",
                ),
            )
    elif row["platform"]:
        # nopCommerce and friends: open endpoint, no sampler. A human look.
        row.update(
            tier="adjudicate",
            verdict="needs_work",
            rank=2,
            reason="%s endpoint, not sampled" % row["platform"],
        )
    else:
        h = hcc.check(host, local)
        row.update(
            url_shape=h["second"] or h["listing"],
            count=None,
            items=[("(html)", h["sample"], None)] if h["sample"] else [],
        )
        if h["tier"] == "html_catalog" and h["local_prices"]:
            row.update(
                tier="accept",
                verdict="ok",
                rank=3,
                platform="html",
                tell="html-catalog %s, %s" % (h["how"], code),
            )
        elif h["tier"] in ("html_catalog", "price_dense"):
            row.update(
                tier="adjudicate",
                verdict="needs_work",
                rank=3,
                platform="html",
                reason="%s, %d local / %d any prices"
                % (h["tier"], h["local_prices"], h["any_prices"]),
            )
        else:
            row.update(
                verdict="no_catalog",
                reason="no_catalog",
                rank=4,
                tell="html tier %s" % h["tier"],
            )

    if row["tier"] == "adjudicate":
        row["title"] = title_of(host)
    return row


def load(args):
    seen, dropped, cands = set(), Counter(), []
    if args.from_sweep:
        rows = [json.loads(line) for line in open(args.from_sweep) if line.strip()]
        raw = [(r.get("href", ""), "ddgs", r.get("q")) for r in rows]
    else:
        raw = []
        for line in open(args.hosts):
            parts = line.rstrip("\n").split("\t")
            if parts[0].strip():
                raw.append(
                    (
                        parts[0].strip(),
                        parts[1] if len(parts) > 1 else None,
                        parts[2] if len(parts) > 2 else None,
                    )
                )
    for ref, method, detail in raw:
        host = (urlparse(ref).netloc if "//" in ref else ref).lower()
        host = host.split(":")[0].removeprefix("www.")
        if not host or "." not in host:
            continue
        if any(host == n or host.endswith("." + n) for n in NOISE):
            dropped["noise"] += 1
            continue
        if host in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(host)
        cands.append(
            {"host": host, "discovery_method": method, "discovery_detail": detail}
        )
    return cands, dropped


def log_row(row, args, today):
    rec = {
        "host": row["host"],
        "probed_at": today.isoformat(),
        "discovery_method": row["discovery_method"],
        "discovery_detail": row["discovery_detail"],
        "platform": row["platform"],
        "url_shape": row["url_shape"],
        "verdict": row["verdict"],
        "lever_tried": row["lever_tried"],
        "tell": row["tell"] if row["tier"] != "adjudicate" else row["reason"],
        "shipped": False,
        "recheck_after": None
        if row["verdict"] == "ok"
        else (today + timedelta(days=180)).isoformat(),
        "rank_predicted": row["rank"],
        "source": "run:%s" % args.run_id,
    }
    return json.dumps(rec, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-sweep", help="ddgs sweep JSONL (rows with q, href)")
    src.add_argument("--hosts", help="host[<TAB>method[<TAB>detail]] per line")
    ap.add_argument("--currency", required=True, help="local ISO code, e.g. FJD")
    ap.add_argument(
        "--symbol", action="append", default=[], help="e.g. FJ$ (repeatable)"
    )
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--country", required=True)
    ap.add_argument("--out", required=True, help="full per-host JSONL")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    cands, dropped = load(args)
    local = hcc.local_price_re(args.currency, args.symbol)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = []
        for row in pool.map(lambda c: triage(c, args.currency, local), cands):
            rows.append(row)
            if len(rows) % 25 == 0:
                print(
                    "  %d / %d triaged" % (len(rows), len(cands)),
                    file=sys.stderr,
                    flush=True,
                )

    today = date.today()
    LOG_DIR.mkdir(exist_ok=True)
    shard = LOG_DIR / ("%s-%s.jsonl" % (args.run_id, args.country))
    with shard.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(log_row(row, args, today) + "\n")
    with open(args.out, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    tiers = Counter(r["tier"] for r in rows)
    reasons = Counter(r["reason"] for r in rows if r["tier"] == "reject")
    print("candidates %d  (dropped: %s)" % (len(cands), dict(dropped) or "none"))
    print(
        "accept %d  adjudicate %d  reject %d  %s"
        % (tiers["accept"], tiers["adjudicate"], tiers["reject"], dict(reasons))
    )
    print("probe log: %s (%d rows)   full rows: %s" % (shard.name, len(rows), args.out))

    print("\n== ACCEPT — scaffold candidates, no reading needed")
    for r in sorted(
        (r for r in rows if r["tier"] == "accept"), key=lambda r: r["rank"]
    ):
        name, price, _ = (r["items"] or [("", "", "")])[0]
        print(
            "  %-32s %-11s %-7s %-6s %s %s"
            % (
                r["host"],
                r["platform"],
                r["count"] or "",
                args.currency,
                price,
                (name or "")[:40],
            )
        )

    print("\n== ADJUDICATE — read these, decide accept / out_of_scope")
    for r in sorted(
        (r for r in rows if r["tier"] == "adjudicate"), key=lambda r: r["rank"]
    ):
        print(
            "  %-32s %-30s %s" % (r["host"], r["reason"], (r.get("title") or "")[:60])
        )
        for name, price, cur in r["items"][:3]:
            print("      %-44s %s %s" % ((name or "")[:44], price, cur or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
