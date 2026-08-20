#!/usr/bin/env python3
"""How much history does Common Crawl hold for one site?

Standalone: Python 3.9+, standard library only. No repo, no pip install, no
credentials. Safe to run on a laptop.

    python3 cc_history_probe.py aldi.com.au --path-prefix /product/
    python3 cc_history_probe.py coles.com.au --path-prefix /product/ --csv coles.csv
    python3 cc_history_probe.py tesco.com --from-year 2016

WHAT IT DOES

Common Crawl is not one archive. It is ~126 separate, immutable crawls, each
with its own independent index. There is no "give me every capture of this
site" endpoint, because there is no cross-crawl notion of a site at all. The
only way to see a site's full history is to ask each crawl separately and
union the answers yourself. That is exactly what this script does.

For every crawl it prints how many captures exist, how many are HTTP 200, how
many sit under the path prefix you care about, and -- the important column --
how many URLs are NEW relative to every crawl already scanned.

READING THE OUTPUT

The NEW column is the point. Common Crawl does not re-crawl the same URLs from
one release to the next; each crawl reaches its own sample of the web. So NEW
typically stays high (often 70-95% of that crawl's URLs) even after dozens of
crawls. Coverage accumulates roughly linearly with crawls scanned, and never
saturates. The practical consequence: scanning a subset of crawls loses
roughly a proportional share of the history. There is no point at which you
have "enough" crawls and can stop early.

WHY IT IS SLOW ON PURPOSE

index.commoncrawl.org tolerates serial access and little else. Measured
2026-08-20: 1 worker succeeded on 24/24 queries; 4 workers drew 503s and
connection refusals; 8 and 12 workers failed 24/24. This script therefore runs
strictly one request at a time with a pause between them. Do not parallelise
it. A full 126-crawl sweep takes roughly 5-15 minutes depending on site size.

NOTES ON MATCHING

Common Crawl canonicalises URLs into SURT form -- the host is reversed and
lowercased and a leading "www." is stripped, and the path is lowercased too:

    https://www.aldi.com.au/Product/X   ->   au,com,aldi)/product/x

So pass the bare registered domain ("aldi.com.au", not "www.aldi.com.au") and
a lowercase path prefix. Subdomains are separate keys: shop.example.com does
NOT match example.com. Use --include-subdomains if you want them.

An HTTP 404 from the index means "no captures matched" -- a normal empty
result for that crawl, not an error.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

COLLINFO = "https://index.commoncrawl.org/collinfo.json"
INDEX_TMPL = "https://index.commoncrawl.org/{crawl}-index"
UA = "pacific-observatory-cc-history-probe/1.0 (World Bank price research)"


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read().decode("utf-8", "replace")


def list_crawls(from_year):
    crawls = json.loads(_get(COLLINFO, timeout=60))
    rows = []
    for c in crawls:
        year = None
        for bit in c["id"].split("-"):
            if len(bit) == 4 and bit.isdigit():
                year = int(bit)
                break
        if from_year and (year is None or year < from_year):
            continue
        rows.append({"id": c["id"], "year": year, "from": c.get("from", "")})
    rows.sort(key=lambda r: r["from"] or r["id"])
    return rows


def query(crawl, pattern, retries=3, pause=8.0):
    """Return the NDJSON body, "" for a legitimate empty result, or None on failure."""
    url = INDEX_TMPL.format(crawl=crawl) + "?" + urllib.parse.urlencode(
        {"url": pattern, "output": "json"}
    )
    for attempt in range(retries):
        try:
            return _get(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return ""  # "No Captures found" -- normal, not an error
            if exc.code in (503, 429, 504) and attempt < retries - 1:
                time.sleep(pause * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(pause * (attempt + 1))
                continue
            return None
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Count Common Crawl captures for one site, crawl by crawl.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n"
               "  python3 cc_history_probe.py aldi.com.au --path-prefix /product/\n",
    )
    ap.add_argument("domain", help="registered domain, e.g. aldi.com.au (no scheme, no www.)")
    ap.add_argument("--path-prefix", default="/",
                    help="restrict to this lowercase path prefix, e.g. /product/ "
                         "(default: the whole site)")
    ap.add_argument("--include-subdomains", action="store_true",
                    help="also match shop.example.com etc. (ignores --path-prefix)")
    ap.add_argument("--from-year", type=int, default=None,
                    help="skip crawls older than this year (default: all, back to 2008)")
    ap.add_argument("--pause", type=float, default=1.5,
                    help="seconds between requests (default 1.5; do not lower)")
    ap.add_argument("--csv", metavar="PATH", help="also write the per-crawl table as CSV")
    args = ap.parse_args()

    domain = args.domain.strip().lower()
    for pre in ("https://", "http://"):
        if domain.startswith(pre):
            domain = domain[len(pre):]
    if domain.startswith("www."):
        domain = domain[4:]
    domain = domain.rstrip("/")

    if args.include_subdomains:
        pattern = "*." + domain
        prefix = ""
    else:
        prefix = args.path_prefix.lower()
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        pattern = domain + "/*" if prefix == "/" else domain + prefix.rstrip("/") + "/*"

    crawls = list_crawls(args.from_year)
    if not crawls:
        print("no crawls selected", file=sys.stderr)
        return 1

    print("site      : %s" % domain)
    print("pattern   : %s" % pattern)
    print("crawls    : %d  (%s .. %s)" % (len(crawls), crawls[0]["id"], crawls[-1]["id"]))
    print("pacing    : serial, %.1fs between requests" % args.pause)
    print()
    hdr = ("%-22s%6s%10s%9s%9s%9s%9s%12s"
           % ("crawl", "year", "captures", "http200", "inScope", "uniqURL", "NEW", "cumulative"))
    print(hdr)
    print("-" * len(hdr))

    seen = set()
    rows = []
    failures = []
    t0 = time.time()

    for c in crawls:
        body = query(c["id"], pattern)
        if body is None:
            failures.append(c["id"])
            print("%-22s%6s  FETCH FAILED -- not counted" % (c["id"], c["year"] or ""))
            time.sleep(args.pause)
            continue

        captures = http200 = inscope = 0
        urls = set()
        for line in body.splitlines():
            if not line.startswith("{"):
                continue
            captures += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("status") != "200":
                continue
            http200 += 1
            path = urllib.parse.urlparse(rec.get("url", "")).path.lower()
            if prefix and prefix != "/" and not path.startswith(prefix):
                continue
            inscope += 1
            urls.add(path.rstrip("/") or "/")

        new = len(urls - seen)
        seen |= urls
        rows.append({
            "crawl": c["id"], "year": c["year"], "captures": captures,
            "http200": http200, "in_scope": inscope, "unique_urls": len(urls),
            "new_urls": new, "cumulative_unique": len(seen),
        })
        print("%-22s%6s%10d%9d%9d%9d%9d%12d"
              % (c["id"], c["year"] or "", captures, http200, inscope,
                 len(urls), new, len(seen)))
        time.sleep(args.pause)

    total_new = sum(r["new_urls"] for r in rows)
    total_uniq = sum(r["unique_urls"] for r in rows)
    print("-" * len(hdr))
    print("\nscanned %d crawls in %.0fs" % (len(rows), time.time() - t0))
    print("distinct URLs recovered  : %s" % format(len(seen), ","))
    if total_uniq:
        print("average novelty per crawl: %.1f%% of each crawl's URLs were unseen before it"
              % (100.0 * total_new / total_uniq))
    nonzero = [r for r in rows if r["unique_urls"]]
    if nonzero:
        print("crawls with any coverage : %d of %d (%s .. %s)"
              % (len(nonzero), len(rows), nonzero[0]["crawl"], nonzero[-1]["crawl"]))
        best = max(nonzero, key=lambda r: r["unique_urls"])
        print("richest single crawl     : %s with %s URLs (%.1f%% of the total)"
              % (best["crawl"], format(best["unique_urls"], ","),
                 100.0 * best["unique_urls"] / max(1, len(seen))))
        print("\nIf you had scanned only %s, you would have %s of %s URLs -- missing %s."
              % (best["crawl"], format(best["unique_urls"], ","),
                 format(len(seen), ","), format(len(seen) - best["unique_urls"], ",")))
    if failures:
        print("\n%d crawls failed to fetch and are NOT in the totals: %s%s"
              % (len(failures), ", ".join(failures[:10]),
                 " ..." if len(failures) > 10 else ""))
        print("Re-run to fill them in; the numbers above are a floor, not a ceiling.")

    if args.csv and rows:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("\nwrote %s" % args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
