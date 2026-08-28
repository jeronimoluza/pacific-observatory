"""Wire the microdata tier into the archived-HTML ladder in template-repo.

This session is worktree-isolated and cannot write to template-repo through
the editing tools, so the change ships as an applier. Idempotent.

    python infra/microdata/apply_microdata.py [--check]

**Microdata goes last, and that placement is the whole safety argument.** The
miss corpus contains only pages the shipped ladder already fails on, so it can
measure what microdata gains but is structurally blind to what an earlier
placement might cost on a page that parses today. Appending a rung changes the
result for exactly the pages that currently return nothing, so the measured
+1,121 pages of 8,744 is pure gain with no regression surface at all.

If microdata later turns out to be *better* than the meta tier rather than
merely additional, promoting it is a separate change that needs its own
measurement on pages that currently succeed.
"""
import argparse
import os
import sys

REPO = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo"
FETCHER = REPO + "/src/prices/cc_warc_fetcher.py"

OLD_IMPORT = ("from .price_scraping.archived import row_from_meta, "
              "rows_from_jsonld")
NEW_IMPORT = ("from .price_scraping.archived import row_from_meta, "
              "rows_from_jsonld\nfrom .price_scraping.archived_microdata "
              "import rows_from_microdata")

OLD_TIERS = '''    def _generic_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Spider-independent tiers: schema.org/OpenGraph, then Next.js flight.

        These surfaces are standardised, so they survive the site redesigns
        that invalidate a spider's era-specific selectors. That makes them the
        right last resort for archived HTML of any age.
        """
        rows = rows_from_jsonld(html, url)
        if rows:
            return rows
        row = row_from_meta(html, url)
        if row:
            return [row]
        return rows_from_next_flight(html, url)'''

NEW_TIERS = '''    def _generic_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Spider-independent tiers: schema.org/OpenGraph, Next.js flight, then
        inline microdata.

        These surfaces are standardised, so they survive the site redesigns
        that invalidate a spider's era-specific selectors. That makes them the
        right last resort for archived HTML of any age.

        Microdata is last on purpose. It is the era-appropriate tier -- 1.71x
        uplift on pre-2020 captures against 1.04x on 2023+ -- but it was
        measured only on pages the tiers above already fail, so appending it
        is the one placement that cannot change a page that parses today.
        """
        rows = rows_from_jsonld(html, url)
        if rows:
            return rows
        row = row_from_meta(html, url)
        if row:
            return [row]
        rows = rows_from_next_flight(html, url)
        if rows:
            return rows
        return rows_from_microdata(html, url)'''

PAIRS = [
    (OLD_IMPORT, NEW_IMPORT, "import"),
    (OLD_TIERS, NEW_TIERS, "generic ladder"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(FETCHER):
        print("missing: %s" % FETCHER)
        return 1
    with open(FETCHER, encoding="utf-8") as fh:
        src = fh.read()

    out = src
    changed = False
    for old, new, label in PAIRS:
        if new in out:
            print("  %-18s already applied" % label)
            continue
        if old not in out:
            print("  %-18s ANCHOR NOT FOUND -- file has drifted" % label)
            return 2
        out = out.replace(old, new, 1)
        changed = True
        print("  %-18s patched" % label)

    if args.check:
        print("\n--check: nothing written")
        return 0
    if changed:
        with open(FETCHER, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("\nwrote %s" % FETCHER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
