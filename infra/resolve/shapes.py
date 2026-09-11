"""Cluster archived paths into URL 'shapes' so a product-page family can be
recognised across eras instead of guessed from today's live scheme.

The ranking signal is DISTINCT-URL CARDINALITY, not raw record count: a site
has a handful of category pages captured many times and thousands of product
pages captured once or twice, so the widest shape is the product family.
"""
import re, collections

NOISE = re.compile(
    r"^/(robots\.txt|sitemap|favicon|wp-|feed|rss|blog/?$|about|contact|terms|"
    r"privacy|login|register|cart|checkout|search|static|assets|css|js|img)",
    re.I,
)
UUID  = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
HEX   = re.compile(r"^[0-9a-f]{16,}$", re.I)
NUM   = re.compile(r"^\d+$")
IDSUF = re.compile(r"^(.*[a-z])-(\d{4,})$", re.I)   # slug-12345
NUMPRE= re.compile(r"^(\d{3,})-([a-z].*)$", re.I)   # 12345-slug


def seg_kind(s):
    if not s:              return ""
    if NUM.match(s):       return "<num>"
    if UUID.match(s):      return "<uuid>"
    if HEX.match(s):       return "<hex>"
    if IDSUF.match(s):     return "<slug-id>"
    if NUMPRE.match(s):    return "<id-slug>"
    if re.fullmatch(r"[A-Za-z0-9_.%-]+", s):
        return s if len(s) <= 24 and not re.search(r"\d{3,}", s) else "<slug>"
    return "<slug>"


def shape(path):
    segs = path.split("/")[1:]
    trail = "/" if path.endswith("/") and len(segs) > 1 else ""
    if trail: segs = segs[:-1]
    return "/" + "/".join(seg_kind(s) for s in segs) + trail


def rank(paths, min_card=4):
    """Shapes ordered by distinct-URL cardinality, noise filtered out."""
    by = collections.defaultdict(set)
    for p in paths:
        if NOISE.match(p): continue
        by[shape(p)].add(p)
    rows = [(sh, len(v)) for sh, v in by.items() if len(v) >= min_card]
    return sorted(rows, key=lambda r: -r[1])


_LIT = {"<num>": r"\d+", "<uuid>": r"[0-9a-f-]{36}", "<hex>": r"[0-9a-f]{16,}",
        "<slug-id>": r"[^/]+-\d{4,}", "<id-slug>": r"\d{3,}-[^/]+", "<slug>": r"[^/]+"}


def to_regex(sh):
    trail = sh.endswith("/") and len(sh) > 1
    body = sh[:-1] if trail else sh
    parts = [ _LIT.get(s, re.escape(s)) for s in body.split("/")[1:] ]
    return "^/" + "/".join(parts) + ("/$" if trail else "$")


def common_prefix(shapes):
    """Longest literal leading path shared by every shape (for archive_prefix)."""
    segs = [s.split("/")[1:] for s in shapes]
    out = []
    for i in range(min(len(s) for s in segs)):
        col = {s[i] for s in segs}
        if len(col) == 1 and not col.pop().startswith("<"):
            out.append(segs[0][i])
        else:
            break
    return "/".join(out)
