"""Why does the prototype microdata tier pick the wrong product name?

The autopsy measured microdata as 96.7% of recoverable misses, but scored the
*gross* number: otto_de names 86% of its converted rows `variationId` and
ebay_uk picks up breadcrumb text 37% of the time, which is why +707k gross is
only ~+467k usable. The prototype takes the first `itemprop="name"` anywhere
under the Product element, so this reports what that element actually is --
its tag, its own attributes, and which itemscope it really belongs to.

Design the scoping rule from the output, do not guess it.
"""
import collections
import gzip
import json
import sys

from bs4 import BeautifulSoup

SHARD = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/miss_shard0.jsonl.gz"
WATCH = {"otto_de", "ebay_uk"}


def prop(el, attr):
    v = el.get(attr)
    if isinstance(v, list):
        v = " ".join(v)
    return (v or "").strip().lower()


def value(el):
    v = el.get("content")
    if v:
        return v
    if el.name in ("meta", "link"):
        return el.get("href") or None
    return el.get_text(" ", strip=True) or None


def owning_scope(el, root):
    """Nearest ancestor carrying itemscope -- the item this prop belongs to."""
    cur = el.parent
    while cur is not None:
        if cur.has_attr("itemscope") or cur.has_attr("itemtype"):
            return cur
        if cur is root:
            return root
        cur = cur.parent
    return None


def main():
    seen = collections.Counter()
    shapes = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)

    for line in gzip.open(SHARD, "rt", encoding="utf-8"):
        rec = json.loads(line)
        spider = rec.get("s")
        if spider not in WATCH:
            continue
        soup = BeautifulSoup(rec["html"], "html.parser")
        scope = None
        for el in soup.find_all(attrs={"itemtype": True}):
            if "schema.org/product" in prop(el, "itemtype"):
                scope = el
                break
        if scope is None:
            continue
        seen[spider] += 1
        for el in scope.find_all(attrs={"itemprop": True}):
            if prop(el, "itemprop") != "name":
                continue
            own = owning_scope(el, scope)
            own_type = prop(own, "itemtype").rsplit("/", 1)[-1] if own else "?"
            direct = own is scope
            shape = "%s tag=%s direct=%s owner=%s" % (
                "FIRST", el.name, direct, own_type or "none")
            shapes[spider][shape] += 1
            if len(examples[spider]) < 6:
                examples[spider].append(
                    (el.name, direct, own_type, str(value(el))[:60]))
            break

    for spider in sorted(seen):
        print("\n=== %s  (%d pages with a Product scope)" % (spider, seen[spider]))
        for shape, n in shapes[spider].most_common(8):
            print("   %-58s %d" % (shape, n))
        print("   examples:")
        for tag, direct, own_type, val in examples[spider]:
            print("     tag=%-6s direct=%-5s owner=%-14s %r"
                  % (tag, direct, own_type or "none", val))
    return 0


if __name__ == "__main__":
    sys.exit(main())
