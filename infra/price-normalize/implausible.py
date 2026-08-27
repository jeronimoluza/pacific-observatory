"""Is the dot-thousands defect actually firing in collected data?

A `78.000` VND price read as `78.0` leaves a fingerprint that needs no raw
strings to detect: a mass of implausibly small values in currencies whose
smallest real price is in the thousands. If the defect fires, VND/IDR/CLP/COP
rows will pile up under 1000 AND concentrate on values with a .0 fraction.

Reads the published price table rather than raw items, because that is where a
corrupted value would actually land.
"""
import collections
import csv
import os
import sys

csv.field_size_limit(10 ** 9)
P = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/outputs/prices/"

# smallest plausible retail unit price, by currency
FLOOR = {"VND": 1000, "IDR": 500, "CLP": 100, "COP": 200, "KRW": 100,
         "PYG": 500, "ISK": 50, "JPY": 20, "HUF": 20, "IRR": 1000,
         "LAK": 500, "KHR": 100, "MMK": 100, "UZS": 500}

path = None
for cand in ("all_countries_prices.csv", "eap_prices.csv"):
    if os.path.exists(P + cand):
        path = P + cand
        break
if not path:
    print("no price table found")
    sys.exit(1)
print("reading %s" % os.path.basename(path))

tot = collections.Counter()
small = collections.Counter()
small_int = collections.Counter()
ex = collections.defaultdict(list)

with open(path, encoding="utf-8", errors="replace") as fh:
    rd = csv.DictReader(fh)
    cols = rd.fieldnames or []
    ccol = next((c for c in cols if c.lower() in ("currency", "currency_code")), None)
    pcol = next((c for c in cols if c.lower() in ("price", "price_value", "value")), None)
    ncol = next((c for c in cols if "name" in c.lower()), None)
    print("columns: currency=%s price=%s name=%s" % (ccol, pcol, ncol))
    if not (ccol and pcol):
        print("cannot locate columns; available: %s" % cols[:25])
        sys.exit(1)
    for row in rd:
        cur = (row.get(ccol) or "").strip().upper()
        if cur not in FLOOR:
            continue
        try:
            v = float(row.get(pcol) or "")
        except ValueError:
            continue
        if v <= 0:
            continue
        tot[cur] += 1
        if v < FLOOR[cur]:
            small[cur] += 1
            # the signature of a mangled dot-thousands value: it kept a
            # fractional part that a real integer-currency price never has
            if v != int(v) or v == int(v):
                small_int[cur] += 1
            if len(ex[cur]) < 6:
                ex[cur].append((v, (row.get(ncol) or "")[:44]))

print()
print("%-5s %10s %10s %8s" % ("cur", "rows", "below floor", "share"))
for cur in sorted(tot, key=lambda c: -tot[c]):
    n, s = tot[cur], small[cur]
    print("%-5s %10d %10d %7.2f%%" % (cur, n, s, 100 * s / n if n else 0))

print()
for cur in sorted(ex):
    if not ex[cur]:
        continue
    print("%s examples (floor %d):" % (cur, FLOOR[cur]))
    for v, nm in ex[cur]:
        print("    %12.4f  %s" % (v, nm))
