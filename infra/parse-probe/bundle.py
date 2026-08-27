"""Stage the three parse modules for the probe.

They are self-contained (stdlib + bs4), so the probe carries them alone rather
than the whole `prices` package, which would drag in scrapy and per-spider
config for a path that covers 0.4% of records.

`selectors.py` is renamed to `selectors_mod.py`: `selectors` shadows a stdlib
module name on the import path the probe uses.
"""
import os
import re
import shutil
import sys

SRC = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src/prices/"
       "price_scraping/")
DEST = sys.argv[1] if len(sys.argv) > 1 else "/tmp/parse"

os.makedirs(DEST, exist_ok=True)
for src_name, dst_name in [("archived.py", "archived.py"),
                           ("archived_embedded.py", "archived_embedded.py"),
                           ("selectors.py", "selectors_mod.py")]:
    text = open(SRC + src_name).read()
    # flatten package-relative imports: the probe puts these on sys.path directly
    text = re.sub(r"^from \.archived import", "from archived import", text, flags=re.M)
    text = re.sub(r"^from \.selectors import", "from selectors_mod import", text, flags=re.M)
    open(os.path.join(DEST, dst_name), "w").write(text)
    print("staged %-24s -> %s (%d lines)" % (src_name, dst_name, text.count("\n")))

shutil.make_archive(DEST.rstrip("/"), "gztar", DEST)
print("bundle: %s.tar.gz (%d bytes)" % (DEST.rstrip("/"),
                                        os.path.getsize(DEST.rstrip("/") + ".tar.gz")))
