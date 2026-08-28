"""Stage the parse modules the EC2 fetch needs, flattened for a bare sys.path.

Four self-contained modules (stdlib + lxml) rather than the whole `prices`
package: importing the package drags in scrapy, pydantic and every per-spider
config to reach `parse_html` hooks that cover 0.4% of records.

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
    ("selectors.py", "selectors_mod.py"),
]

REWRITES = [
    (r"^from \.archived import", "from archived import"),
    (r"^from \.archived_ldrepair import", "from archived_ldrepair import"),
    (r"^from \.archived_microdata import", "from archived_microdata import"),
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
