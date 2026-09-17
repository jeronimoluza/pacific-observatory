"""One seller registered twice, as data rather than a branch in the hash.

Scope-module step 4 folds `source` into `input_hash` so that "re-run source X"
means "rows collected by X" rather than "rows where X won a tie-break". That is
right for the normal case and wrong for the handful of sellers registered under
two source names: their rows are the SAME observations, today collapsed into one
product because the hash ignores source, and folding source in would split them
into two products and double-count the seller.

The fix is a map applied before hashing, not an exemption inside it. The hash
function stays uniform with no special case, and "two configs, one seller"
becomes a row of data with its evidence beside it.

**How a pair gets in here -- both conditions, never one.**

1. The two manifests declare the **same `url`**, so they are the same
   registration rather than two merchants on one platform. A source with no
   manifest at all is admitted against the manifest of the source it duplicates.
2. Their identity sets measurably overlap, replayed over the real corpus.

Condition 1 is what carries the weight, and the corpus is why. Measured
2026-09-17 over the 2,333 post-quarantine shards, 39 source pairs share any
identity at all, and overlap ALONE cannot separate the two cases: the genuine
duplicates land at 0.97-1.00 and the marketplace cliques at 0.50-0.95, bands
that very nearly touch. `mysamoa_chan_mow_ws`/`mysamoa_sulas_ws` overlap 0.95 and
are two different Samoan supermarkets; `hepsiburada_com`/`hepsiburada_tr` overlap
0.97 and are one Turkish storefront. No threshold separates those. The declared
url does, cleanly, and it separates every other pair too -- the four `costuless`
islands, the four purpose-built `o4a2` collections, and
`konalivr_gn`/`konalivr_supermarket_gn` all declare different urls and all stay
apart.

Name similarity is a candidate generator only. It cannot be the test:
`carrefour_fr` and `carrefour_tw` share a stem, share no identities, and
canonicalising on that signal would be destructive.
"""

from __future__ import annotations

# source name -> the name its rows are hashed under.
#
# `shared` is distinct identities in common and `of smaller` is that as a
# fraction of the smaller source's distinct identities, both measured on the
# post-quarantine corpus, 2026-09-17.
CANONICAL: dict[str, str] = {
    # --- o4a2.com: eight Tongan manifests, one registration -----------------
    # All eight declare `https://o4a2.com/` -- the site ROOT -- and all eight
    # name the SAME generic spider, `o4a2_to`. So each one scrapes the whole
    # marketplace and keeps a slice of it, which is why four of them are pure
    # subsets of `o4a2_to` at 1.00 and the rest sit at 0.72-0.76.
    #
    # Today's hash already collapses these rows. Folding source in WITHOUT this
    # map would mint 2,021 duplicate Tongan products -- roughly a third of the
    # country -- out of a collect-layer defect. Canonicalising reproduces
    # today's behaviour exactly and adds nothing new.
    #
    # This is a workaround, not a repair. The repair is to stop six manifests
    # sharing one site-root spider, and it belongs in collect. Revisit this
    # block when that lands; the four purpose-built `o4a2_*` collection
    # manifests already scrape their own merchant and are deliberately absent.
    "bako_store_to": "o4a2_to",          # shared    160, of smaller 1.00
    "elenoa_store_to": "o4a2_to",        # shared    113, of smaller 1.00
    "pingi_store_to": "o4a2_to",         # shared    180, of smaller 1.00
    "rainbow_top_to": "o4a2_to",         # shared    356, of smaller 1.00
    "hihifo_supermarket_to": "o4a2_to",  # shared    546, of smaller 0.76
    "golden_star_to": "o4a2_to",         # shared    533, of smaller 0.73
    "pepe_pusiaki_to": "o4a2_to",        # shared    133, of smaller 0.72
    # --- one storefront, two manifests --------------------------------------
    # `seria.supasave.com.bn` registered twice: a spider and a fetcher. Every
    # one of supasave_bn's identities is in supasave_seria's. The spider keeps
    # the name, which is also how the Common Crawl claim was resolved.
    "supasave_seria": "supasave_bn",     # shared  3,870, of smaller 1.00
    # `www.nubrimart.com` registered twice; the `<name>_<cc>` spelling wins.
    "nepal_nubrimart": "nubrimart_np",   # shared      8, of smaller 1.00
    # `himawarisaipan.com/menu` registered twice under two spellings of the
    # same name. 0.58 rather than 1.00 because a menu scraped on different days
    # is not the same set of dishes, not because they are different restaurants.
    "himawari_saipan": "himawarisaipan_mp",  # shared 295, of smaller 0.58
    # --- orphan source directories, no manifest at all ----------------------
    # Both sit in eca/turkiye/turkiye beside the manifest they duplicate and
    # are almost certainly an older spelling of its source key. They still feed
    # the corpus, so they still need a home in the hash.
    "n11_com": "n11_tr",                 # shared    100, of smaller 1.00
    "hepsiburada_com": "hepsiburada_tr",  # shared   226, of smaller 0.97
}


def canonical_source(source) -> str:
    """The name `source`'s rows are hashed under. Unmapped names pass through.

    Missing or null reads as the empty string: a hash is computed for every raw
    row, so a row with no source still has to get one."""
    if source is None or source != source:  # NaN
        return ""
    name = str(source)
    return CANONICAL.get(name, name)
