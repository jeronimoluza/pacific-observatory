"""Export the per-source resolve config the EC2 job needs.

The instance has no repo, so the 623 (spider -> prefix, path_re) triples travel
as one small JSON alongside the code. surt_prefix is applied here, using the
repo's own implementation, so the instance never has to reimplement CC's
canonicalisation (dropping `www.`, lowercasing the path) and cannot drift from
what produced the 22 manifests already on disk.
"""
import json
import os
import sys

sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")
os.chdir("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo")

from prices.cc_index import surt_prefix  # noqa: E402
from prices.cc_config import all_cc_configs  # noqa: E402

cfgs = all_cc_configs()
out = []
for spider, c in sorted(cfgs.items()):
    prefix = c.get("prefix")
    if not prefix:
        continue
    out.append({
        "spider": spider,
        "prefix": prefix,
        "surt": surt_prefix(prefix),
        "path_re": c.get("path_re") or "",
    })

dst = "/Users/jeronimoluza/.claude/jobs/f8501cf5/tmp/pricefmt/sources.json"
json.dump(out, open(dst, "w"))
print("sources: %d" % len(out))
print("distinct surt prefixes: %d" % len({o["surt"] for o in out}))
print("with a path_re: %d" % sum(1 for o in out if o["path_re"]))
print()
for o in out[:5]:
    print("  %-22s %-46s %s" % (o["spider"], o["surt"], o["path_re"][:30]))
print("wrote %s" % dst)
