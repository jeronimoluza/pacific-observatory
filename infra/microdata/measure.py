"""What does the microdata tier actually add, and are the names usable?

Runs over the archived miss corpus -- pages the shipped ladder could not read.
Reports three things, because the autopsy's headline (+707k gross) was not the
bankable number:

1. recovery: how many miss pages yield a row once microdata is added, split by
   what recovers them, so the JSON-LD repair applied earlier is not
   double-counted as a microdata win;
2. name quality per source, which is where the gross figure leaked -- a row
   named `variationId` or `Sound & Vision` is not a usable observation;
3. cost, since this tier runs on every page the others miss.
"""
import collections
import glob
import gzip
import json
import sys
import time

sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")

from prices.price_scraping.archived import (  # noqa: E402
    rows_from_jsonld, row_from_meta,
)
from prices.price_scraping.archived_embedded import (  # noqa: E402
    rows_from_next_flight,
)
from prices.price_scraping.archived_microdata import (  # noqa: E402
    rows_from_microdata,
)

SHARDS = sorted(glob.glob(
    "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_html/*.jsonl.gz"))

# Names the autopsy caught the naive scoping producing. Not a filter in the
# shipped code -- a tripwire here, so a regression shows up as a number.
BAD_TOKENS = {"variationid", "productid", "sku", "name", "title", "value"}


def shipped(html, url):
    """The generic ladder as it stands, microdata excluded."""
    rows = rows_from_jsonld(html, url)
    if rows:
        return rows, "jsonld"
    row = row_from_meta(html, url)
    if row:
        return [row], "meta"
    rows = rows_from_next_flight(html, url)
    if rows:
        return rows, "flight"
    return [], "none"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    n = 0
    base_hit = 0
    micro_new = 0
    by_tier = collections.Counter()
    names_by_source = collections.defaultdict(list)
    bad_by_source = collections.Counter()
    tot_by_source = collections.Counter()
    t_micro = 0.0

    for path in SHARDS:
        for line in gzip.open(path, "rt", encoding="utf-8"):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            n += 1
            html, url, src = rec["html"], rec["u"], rec.get("s") or "?"
            try:
                rows, tier = shipped(html, url)
            except Exception:
                rows, tier = [], "error"
            by_tier[tier] += 1
            if rows:
                base_hit += 1
                continue
            t0 = time.time()
            try:
                mrows = rows_from_microdata(html, url)
            except Exception:
                mrows = []
            t_micro += time.time() - t0
            if not mrows:
                continue
            micro_new += 1
            for r in mrows:
                nm = (r.get("product_name") or "").strip()
                tot_by_source[src] += 1
                names_by_source[src].append(nm)
                if nm.lower() in BAD_TOKENS or len(nm) < 3:
                    bad_by_source[src] += 1
            if limit and n >= limit:
                break
        if limit and n >= limit:
            break

    print("miss pages read            %d" % n)
    print("already readable now       %d (%.1f%%)  <- JSON-LD repair etc"
          % (base_hit, 100.0 * base_hit / max(n, 1)))
    print("   by tier                 %s" % dict(by_tier))
    print("recovered by microdata     %d (%.1f%% of all miss pages)"
          % (micro_new, 100.0 * micro_new / max(n, 1)))
    still = n - base_hit - micro_new
    print("still unreadable           %d (%.1f%%)"
          % (still, 100.0 * still / max(n, 1)))
    print("microdata cost             %.2f ms/page attempted"
          % (1000.0 * t_micro / max(n - base_hit, 1)))

    print("\nname quality on microdata rows (top 14 sources)")
    print("  %-22s %6s %6s %8s  %s" % ("source", "rows", "bad", "distinct", "sample"))
    for src, tot in tot_by_source.most_common(14):
        names = names_by_source[src]
        distinct = len(set(names)) / max(len(names), 1)
        sample = next((x for x in names if x), "")
        print("  %-22s %6d %6d %8.2f  %r"
              % (src, tot, bad_by_source[src], distinct, sample[:44]))

    tot = sum(tot_by_source.values())
    bad = sum(bad_by_source.values())
    print("\ntotal microdata rows       %d" % tot)
    print("unusable names             %d (%.2f%%)"
          % (bad, 100.0 * bad / max(tot, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
