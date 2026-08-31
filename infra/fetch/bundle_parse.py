"""Stage the parse modules the EC2 fetch needs, flattened for a bare sys.path.

Self-contained modules (stdlib + lxml) rather than the whole `prices` package:
importing the package drags in scrapy, pydantic and every per-spider config to
reach `parse_html` hooks that cover 0.4% of records.

The per-source tier is bundled even though it is spider-keyed, because it is
not those hooks and the weight calculus is not theirs. `archived_bysource.py`
and the two modules it dispatches into cover seven sources holding 6,378,103 of
17,154,784 misses -- 37.2% -- and depend on nothing outside lxml, so they cost
three files rather than the whole package. Leaving them out was the same as
launching with no per-source fix at all.

`selectors.py` is renamed to `selectors_mod.py` because `selectors` shadows a
stdlib module on a bare sys.path, and the package-relative imports are rewritten
to flat ones.
"""
import os
import re
import shutil
import sys

SRC = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src/prices/"
       "price_scraping/")
DEST = sys.argv[1] if len(sys.argv) > 1 else "/tmp/parse"

FILES = [
    ("archived.py", "archived.py"),
    ("archived_embedded.py", "archived_embedded.py"),
    ("archived_ldrepair.py", "archived_ldrepair.py"),
    ("archived_microdata.py", "archived_microdata.py"),
    ("archived_nextdata.py", "archived_nextdata.py"),
    ("archived_livingcost.py", "archived_livingcost.py"),
    ("archived_lohaco.py", "archived_lohaco.py"),
    ("archived_eu.py", "archived_eu.py"),
    ("archived_gmarket.py", "archived_gmarket.py"),
    ("archived_chemist.py", "archived_chemist.py"),
    ("archived_classifieds.py", "archived_classifieds.py"),
    ("archived_ekupi.py", "archived_ekupi.py"),
    ("archived_emart.py", "archived_emart.py"),
    ("archived_yahoo_tw.py", "archived_yahoo_tw.py"),
    ("archived_momo.py", "archived_momo.py"),
    ("archived_frisco.py", "archived_frisco.py"),
    ("archived_bysource.py", "archived_bysource.py"),
    ("selectors.py", "selectors_mod.py"),
]

# One rule for every `archived*` module rather than one per module. Naming them
# individually meant adding a source could stage a file whose own import was
# left package-relative, and the per-source tier had already been lost once to
# exactly that class of omission. The leftover check below still fails the
# build on anything this does not flatten, so the general rule is not a
# loosening.
REWRITES = [
    (r"^from \.(archived\w*) import", r"from \1 import"),
    (r"^from \.selectors import", "from selectors_mod import"),
]


def main():
    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST, exist_ok=True)
    for src_name, dst_name in FILES:
        path = SRC + src_name
        if not os.path.exists(path):
            print("MISSING %s" % path)
            return 1
        text = open(path, encoding="utf-8").read()
        for pat, repl in REWRITES:
            text = re.sub(pat, repl, text, flags=re.M)
        leftover = re.findall(r"^from \.\w+ import.*$", text, flags=re.M)
        if leftover:
            print("UNFLATTENED import in %s: %s" % (dst_name, leftover))
            return 1
        open(os.path.join(DEST, dst_name), "w", encoding="utf-8").write(text)
        print("staged %-24s -> %-24s %d lines"
              % (src_name, dst_name, text.count("\n")))

    root = DEST.rstrip("/")
    shutil.make_archive(root, "gztar", DEST)
    print("bundle: %s.tar.gz (%d bytes)"
          % (root, os.path.getsize(root + ".tar.gz")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
