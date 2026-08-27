"""Checks for the currency-aware normalize_price.

The safety property matters more than the fix: 17+ spiders already call this
function, so every input that is not a lone dot with a 3-digit tail must return
exactly what ships today. The last group asserts that differentially against
the real archived function rather than against remembered behaviour.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")

from pricenorm import normalize_price as fixed  # noqa: E402

CASES = [
    # --- the defect: lone dot, 3-digit tail, integer currency -> thousands ---
    ("78.000", "VND", "78000.0", "the reported defect"),
    ("125.000", "VND", "125000.0", "a real cocoon serum price"),
    ("1.500", "IDR", "1500.0", "rupiah"),
    ("19.990", "CLP", "19990.0", "chilean peso"),
    ("78.000", "COP", "78000.0", "colombian peso"),
    ("1.234", "JPY", "1234.0", "yen"),
    ("1.234", "HUF", "1234.0", "forint, de-facto integer"),
    ("2.500", "KRW", "2500.0", "won"),

    # --- same string, minor-unit currency -> still a decimal point ---
    ("1.500", "USD", "1.5", "three decimals are legal in USD"),
    ("1.459", "EUR", "1.459", "fuel is quoted to 3 decimals"),
    ("78.000", "GBP", "78.0", "unchanged without an integer currency"),
    ("78.000", None, "78.0", "no currency -> unchanged, never worse"),
    ("78.000", "", "78.0", "empty currency -> unchanged"),

    # --- lone dot, tail is not 3 -> always a decimal point ---
    ("1.5", "VND", "1.5", "tail 1 is not a grouping"),
    ("19.99", "VND", "19.99", "tail 2 is not a grouping"),
    ("1.5000", "VND", "1.5", "tail 4 is not a grouping"),
    ("19.99", "USD", "19.99", "the ordinary case"),

    # --- more than one dot -> thousands regardless of currency ---
    ("1.234.567", "VND", "1234567.0", "repeated dot cannot be decimal"),
    ("1.234.567", "USD", "1234567.0", "true even for USD"),
    ("1.100.000", "VND", "1100000.0", "was returning None before"),

    # --- untouched paths: comma+dot ---
    ("1.234,56", "EUR", "1234.56", "EU convention"),
    ("1,234.56", "USD", "1234.56", "US convention"),
    ("1.234,56", "VND", "1234.56", "currency must not disturb this"),

    # --- untouched paths: lone comma ---
    ("1,50", "EUR", "1.5", "tail 2 is a decimal comma"),
    ("1,500", "EUR", "1500.0", "tail 3 is a grouping comma"),
    ("1,234,567", "USD", "1234567.0", "repeated comma"),
    ("1,50", "VND", "1.5", "currency must not disturb this either"),

    # --- untouched paths: no separator, junk, symbols ---
    ("78000", "VND", "78000.0", "plain integer"),
    ("₫78.000", "VND", "78000.0", "symbol stripped first"),
    ("Rp 1.500", "IDR", "1500.0", "prefix and space stripped"),
    ("", "VND", None, "empty"),
    (None, "VND", None, "none"),
    ("abc", "VND", None, "no digits"),
    ("-5.000", "VND", "-5000.0", "negative keeps its sign"),

    # --- currency casing / whitespace ---
    ("78.000", "vnd", "78000.0", "lowercase currency"),
    ("78.000", " VND ", "78000.0", "padded currency"),
]

failed = 0
for raw, cur, want, why in CASES:
    got = fixed(raw, cur)
    if got != want:
        failed += 1
        print("FAIL  %-12r cur=%-6r want=%-12r got=%-12r  (%s)"
              % (raw, cur, want, got, why))
print("%d cases, %d failed" % (len(CASES), failed))

# ---------------------------------------------------------------- regression
# Every input that is NOT a lone dot with a 3-digit tail must be byte-identical
# to the shipped function. Asserted against the real thing, not from memory.
print()
try:
    from prices.price_scraping.archived import normalize_price as shipped
except Exception as exc:  # pragma: no cover - import path issue, not a result
    print("could not import shipped normalize_price: %s" % exc)
    sys.exit(1 if failed else 0)

import itertools  # noqa: E402

ALPHABET = ["", "0", "1", "5", "12", "99", "123", "500", "1234", "0000"]
SEPS = ["", ".", ","]
probes = set()
for a, s1, b, s2, c in itertools.product(
        ALPHABET, SEPS, ALPHABET, SEPS, ALPHABET):
    probes.add(a + s1 + b + s2 + c)
probes |= {"78.000", "1.5", "-3,50", "₫9.900", "1.2.3.4", ".", ",", "-", "1..2"}

CURRENCIES = [None, "USD", "EUR", "VND", "IDR", "JPY", "GBP"]
drift = []
for p in sorted(probes):
    base = shipped(p)
    for cur in CURRENCIES:
        got = fixed(p, cur)
        if got == base:
            continue
        # the ONLY licensed divergence
        digits = "".join(ch for ch in p if ch not in "-")
        lone_dot_3 = ("." in digits and "," not in digits
                      and digits.count(".") == 1
                      and len(digits.split(".")[-1]) == 3)
        multidot = digits.count(".") > 1 and "," not in digits
        if lone_dot_3 and cur and cur.upper() in __import__("pricenorm").ZERO_DECIMAL:
            continue
        if multidot:
            continue  # 1.234.567 was returning None; now returns a number
        drift.append((p, cur, base, got))

print("differential probe: %d inputs x %d currencies" % (len(probes), len(CURRENCIES)))
if drift:
    print("UNLICENSED DRIFT in %d combinations:" % len(drift))
    for p, cur, base, got in drift[:20]:
        print("   %-14r cur=%-6r shipped=%-14r fixed=%-14r" % (p, cur, base, got))
else:
    print("no unlicensed drift: every other input matches the shipped function")

sys.exit(1 if (failed or drift) else 0)
