"""Does the block-major resolver reproduce a manifest the shipped code wrote?

This is the gate before spending anything on the other 101 crawls. The new
resolver reorganises the traversal (block-major, S3, concurrent) and any drift
in prefix matching, status filtering or path_re handling would silently change
which records exist — the exact class of failure that is invisible downstream,
because a smaller manifest still fetches and still parses.

Compared as a multiset keyed on the whole row: traversal order legitimately
differs, record identity must not.

    python verify.py <new.jsonl.gz> <reference.jsonl>
"""
import collections
import gzip
import json
import sys


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    rows = collections.Counter()
    spiders = collections.Counter()
    bad = 0
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                bad += 1
                continue
            key = (d.get("spider"), d.get("url"), d.get("timestamp"),
                   d.get("filename"), d.get("offset"), d.get("length"),
                   d.get("digest"))
            rows[key] += 1
            spiders[d.get("spider")] += 1
    return rows, spiders, bad


def main():
    new_path, ref_path = sys.argv[1], sys.argv[2]
    new, new_sp, new_bad = load(new_path)
    ref, ref_sp, ref_bad = load(ref_path)

    n_new, n_ref = sum(new.values()), sum(ref.values())
    print("new       %-46s %10d rows  %d unparseable" %
          (new_path.split("/")[-1], n_new, new_bad))
    print("reference %-46s %10d rows  %d unparseable" %
          (ref_path.split("/")[-1], n_ref, ref_bad))
    print()

    missing = ref - new      # in the reference, absent from the new run
    extra = new - ref        # produced by the new run only
    n_missing, n_extra = sum(missing.values()), sum(extra.values())

    if not n_missing and not n_extra:
        print("IDENTICAL — %d rows match as a multiset" % n_ref)
        return 0

    print("MISMATCH  missing=%d  extra=%d" % (n_missing, n_extra))
    print()
    by_sp = collections.Counter()
    for key, c in missing.items():
        by_sp[key[0]] += c
    if by_sp:
        print("rows the new run did NOT produce, by spider:")
        for sp, c in by_sp.most_common(12):
            print("   %-24s %8d  (reference has %d)" % (sp, c, ref_sp.get(sp, 0)))
    by_sp = collections.Counter()
    for key, c in extra.items():
        by_sp[key[0]] += c
    if by_sp:
        print()
        print("rows only the new run produced, by spider:")
        for sp, c in by_sp.most_common(12):
            print("   %-24s %8d" % (sp, c))
    print()
    for label, bag in (("MISSING", missing), ("EXTRA", extra)):
        for key in list(bag)[:3]:
            print("  %s %s" % (label, key))
    return 1


if __name__ == "__main__":
    sys.exit(main())
