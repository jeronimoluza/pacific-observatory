#!/usr/bin/env python3
"""Named-chain sweep: search for each brand by name, feed the hits to triage.

Why this exists: a category sweep ("Fiji hardware store online") only returns
what ranks for the category. On the blind Fiji run (2026-09-25) three of the
country's known storefronts never appeared in 615 category results, and every
one of them surfaced on the first query that used its name. A second miss
class is the Botswana one: the brand is found, but on its corporate domain,
and the shop lives on a sibling (shopsefalana.com, not sefalana.co.bw).

Names come from two places:

  --names    one brand per line, written by the agent from what it knows of
             the country's retail (chains, franchises, big independents, across
             the categories). ~50 names costs about 1k output tokens.
  --triage   a previous triage_candidates.py output. Every no_catalog / blocked
             host is a brand whose shop may live elsewhere; its label becomes a
             name ("newworld.com.fj" -> "newworld").

Each name gets two queries. Hits on hosts the previous triage already saw are
dropped, so the output is only new candidates. Hand it to triage:

    ~/venv/bin/python scripts/chain_sweep.py --country Fiji --names names.txt \\
        --triage triage.jsonl --out sweep_chains.jsonl
    ~/venv/bin/python scripts/triage_candidates.py --from-sweep sweep_chains.jsonl \\
        --currency FJD --symbol 'FJ$' --run-id fj2 --country fiji --out triage2.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.parse import urlparse

from ddgs import DDGS

from triage_candidates import NOISE

BACKENDS = "duckduckgo, google, brave, mojeek, startpage, yahoo"
QUERIES = ("{name} {country} online shop", "buy {name} online {country}")
# Second-level labels under a ccTLD, and the institutional ones: a ministry
# with no catalog is not a chain with a storefront somewhere else.
SLD = {"com", "co", "net", "org", "ltd", "biz", "gov", "govt", "ac", "edu", "mil"}
SKIP_SLD = {"gov", "govt", "ac", "edu", "mil", "org"}


def norm(ref):
    host = (urlparse(ref).netloc if "//" in ref else ref).lower()
    return host.split(":")[0].removeprefix("www.")


def brand_of(host):
    """newworld.com.fj -> newworld; shop.prouds.com.fj -> prouds; x.gov.fj -> None."""
    parts = host.split(".")[:-1]
    if any(p in SKIP_SLD for p in parts):
        return None
    while parts and parts[-1] in SLD:
        parts.pop()
    return parts[-1] if parts and len(parts[-1]) > 2 else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--country", required=True, help="as a searcher writes it: Fiji")
    ap.add_argument("--names", help="one brand name per line")
    ap.add_argument("--triage", help="previous triage_candidates.py --out file")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    names, seen = [], set()
    if args.names:
        names += [n.strip() for n in open(args.names) if n.strip()]
    if args.triage:
        for line in open(args.triage):
            r = json.loads(line)
            seen.add(r["host"].removeprefix("www."))
            if r.get("reason") in ("no_catalog", "blocked"):
                b = brand_of(r["host"])
                if b:
                    names.append(b)
    uniq = list(dict.fromkeys(n.lower() for n in names))
    print("names %d, queries %d" % (len(uniq), len(uniq) * len(QUERIES)), flush=True)

    new, zero, streak = set(), 0, 0
    with DDGS() as d, open(args.out, "w") as out:
        for name in uniq:
            for tpl in QUERIES:
                q = tpl.format(name=name, country=args.country)
                # Fiji, 2026-09-26: after ~220 queries in a day, four of six
                # backends answered "No results found" to everything and 132
                # of 136 queries came back empty. Back off once, then stop
                # rather than write a sweep that looks like "no shops".
                for wait in (0, 30):
                    time.sleep(wait)
                    try:
                        res = d.text(q, backend=BACKENDS, max_results=20)
                    except Exception:
                        res = []
                    if res:
                        break
                zero += not res
                streak = 0 if res else streak + 1
                if streak >= 10:
                    print(
                        "10 empty queries in a row: backends are throttling. "
                        "Stopped at %r; re-run later." % q
                    )
                    return 1
                for r in res:
                    host = norm(r.get("href", ""))
                    if not host or host in seen:
                        continue
                    if any(host == n or host.endswith("." + n) for n in NOISE):
                        continue
                    new.add(host)
                    out.write(json.dumps({"q": q, **r}, ensure_ascii=False) + "\n")
                out.flush()
                time.sleep(1.5)
    # A run of zero-result queries means the backends failed, not that the
    # brands have no shop (ddgs_search.md).
    print("new hosts %d, zero-result queries %d -> %s" % (len(new), zero, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
