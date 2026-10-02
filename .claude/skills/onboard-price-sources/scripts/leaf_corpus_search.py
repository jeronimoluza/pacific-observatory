#!/usr/bin/env python3
"""Phase 0.5 for a COICOP-gap request: is the leaf already in our raw data?

Why this exists: on the 2026-09-27 leaf runs (divisions 01-02, 20 missing
leaves each), 18 of 20 Philippines leaves and 19 of 20 Vietnam leaves were
already in products_input.parquet. They were lost at classification or trust,
where no new source can help. Each agent spent most of ~130k tokens proving
that with hand-written regexes, and fought "Tarot" for taro, hair dye for
chestnut, lotion for rice milk.

For each leaf this matches the leaf's labels (the enrich sub-labels, English,
plus any --terms you add in the local language) against the country's raw
product names, drops non-food hits, and follows every match into the build to
say where it went:

  classified_leaf   the classifier got it right; trust/QA dropped it
  classified_other  the classifier put it under another code (named)
  not_built         the row never reached global_prices_observations

A leaf with no matches is the only real discovery target. Run on a8:

    ~/venv/bin/python scripts/leaf_corpus_search.py --country vietnam \\
        --leaves targets.tsv --terms vi_terms.tsv --out leaf_audit.tsv

--leaves takes codes (comma-separated) or a TSV whose first column is the
code. --terms is `leaf<TAB>term` per line, e.g. `01.1.5.1.7<TAB>dầu bắp`.
Read the samples before trusting a match: a label can still hit the wrong
thing, and the samples are there to make that a glance, not an audit.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Words that mark a product as not food, whatever leaf label it contains.
# Each one is a false positive from the 2026-09-27 runs or its neighbour.
NONFOOD = (
    "lotion shampoo conditioner soap scrub serum mask lamp candle perfume "
    "fragrance diffuser toy plush book shirt dress dye hair skin facial "
    "cleanser deodorant nail lip polish sponge brush flask cap case cover "
    "sticker keychain costume pet dog cat essential tinh playset play-doh "
    "dissecting bubble"
).split()
NONFOOD_RE = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(NONFOOD), re.I)
# Menu dishes: "Ham, Cheese, Tomato Toasties" is not bacon and ham. Restaurant
# menus are filed under food channels (cabitfoody_sb is "supermarket"), so the
# dish has to be recognised by name. Not "sauce" or "meal": "Smoked Mussels in
# Sauce" and cornmeal are shelf items.
DISH_RE = re.compile(
    r"(?<!\w)(?:burgers?|wraps?|toasties?|sandwich(?:es)?|salad|soup|combo|"
    r"platter|curry|fried rice|combination)(?!\w)",
    re.I,
)
# Cost-of-living aggregators: one price per item type, not a shelf.
AGGREGATORS = {"livingcost", "expatistan", "mylifeelsewhere", "numbeo"}
# Channels that never carry a food leaf. Not "supermarket": cabitfoody_sb is a
# restaurant menu filed as one, and healthy_options_ph sells food as "pharmacy",
# so the channel can only exclude, never include.
NONFOOD_CHANNELS = {
    "electronics",
    "real-estate",
    "fashion",
    "home-improvement",
    "fuel-station",
    "cosmetics",
    "pet",
}
# The sub-labels are written for a classifier ("fresh fig", "brazil nut in
# shell", "canned sardine"); shelves say "Figs (Australian Grown)". Also match
# each label with these modifiers stripped.
MODIFIERS = re.compile(
    r"\b(?:fresh|chilled|frozen|canned|tinned|shelled|in shell|roasted|salted|"
    r"dried|smoked|prepared|preserved|in brine|whole|raw)\b",
    re.I,
)


def expand(terms):
    out = set()
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        out.add(t)
        bare = " ".join(MODIFIERS.sub(" ", t).split())
        if len(bare) > 2:
            out.add(bare)
    return out


def leaf_regex(terms):
    alts = sorted(expand(terms), key=len, reverse=True)
    # Word boundaries on both sides, optional English plural. Unicode \w keeps
    # Vietnamese diacritics inside the word.
    return re.compile(
        r"(?<!\w)(?:%s)(?:e?s)?(?!\w)" % "|".join(re.escape(a) for a in alts), re.I
    )


def load_leaves(spec):
    p = Path(spec)
    if p.exists():
        df = pd.read_csv(p, sep="\t", dtype=str)
        return [c for c in df.iloc[:, 0] if re.match(r"^\d", str(c))]
    return [c.strip() for c in spec.split(",") if c.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--country", required=True, help="as in the parquet: vietnam")
    ap.add_argument("--leaves", required=True, help="codes, or a TSV of codes")
    ap.add_argument("--terms", help="extra leaf<TAB>term lines, any language")
    ap.add_argument("--root", default=str(Path.home() / "po"), help="repo root")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--out", help="per-leaf TSV")
    args = ap.parse_args()

    root = Path(args.root)
    leaves = load_leaves(args.leaves)
    labels = pd.read_parquet(
        root / "src/prices/enrich/keywords/coicop/_sub_labels.parquet"
    )
    xl = pd.read_excel(root / "data/prices/enrich/coicop_categories.xlsx")
    title = dict(zip(xl["code"].astype(str), xl["title"].astype(str)))

    terms = defaultdict(list)
    for code, label in zip(labels.coicop_code, labels.label):
        if code in leaves:
            terms[code].append(label)
    if args.terms:
        for line in open(args.terms, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2 and parts[0] in leaves:
                terms[parts[0]].append(parts[1])
    for code in leaves:
        if not terms[code]:
            # No label: fall back to the title's head noun phrase.
            terms[code].append(title.get(code, "").split(",")[0])

    corpus = pq.read_table(
        root / "data/prices/enrich/products_input.parquet",
        columns=["product_name_original", "price", "source", "channel"],
        filters=[("country", "=", args.country)],
    ).to_pandas()
    corpus = corpus.dropna(subset=["product_name_original"])
    corpus = corpus[~corpus.channel.isin(NONFOOD_CHANNELS)]
    corpus = corpus[~corpus.source.isin(AGGREGATORS)]
    corpus = corpus[~corpus.product_name_original.str.contains(DISH_RE)]
    corpus = corpus[~corpus.product_name_original.str.contains(NONFOOD_RE)]

    built = pq.read_table(
        root / "data/prices/build/global_prices_observations.parquet",
        columns=["product_name", "source", "coicop_code", "qa_status"],
        filters=[("country", "=", args.country)],
    ).to_pandas()
    built = built.drop_duplicates(["source", "product_name"]).set_index(
        ["source", "product_name"]
    )

    print(
        "%s: %d food-ish raw rows, %d leaves" % (args.country, len(corpus), len(leaves))
    )
    rows = []
    for code in leaves:
        hit = corpus[corpus.product_name_original.str.contains(leaf_regex(terms[code]))]
        where = Counter()
        other = Counter()
        for src, name in zip(hit.source, hit.product_name_original):
            try:
                got = built.loc[(src, name), "coicop_code"]
            except KeyError:
                where["not_built"] += 1
                continue
            if got == code:
                where["classified_leaf"] += 1
            else:
                where["classified_other"] += 1
                other[got] += 1
        verdict = "in_corpus" if len(hit) else "absent"
        srcs = hit.source.value_counts().head(3).to_dict()
        samp = [
            "%s | %s | %s" % (n[:60], p, s)
            for n, p, s in hit.drop_duplicates("product_name_original")
            .head(args.samples)[["product_name_original", "price", "source"]]
            .values
        ]
        rows.append(
            dict(
                leaf=code,
                title=title.get(code, "")[:50],
                terms=sorted(expand(terms[code])),
                verdict=verdict,
                rows=len(hit),
                sources=srcs,
                classified_leaf=where["classified_leaf"],
                classified_other=where["classified_other"],
                top_other=other.most_common(2),
                not_built=where["not_built"],
                samples=samp,
            )
        )

    for r in sorted(rows, key=lambda r: (r["verdict"] != "absent", r["leaf"])):
        print(
            "\n%s  %s  [%s] rows=%d  leaf=%d other=%d%s not_built=%d"
            % (
                r["leaf"],
                r["title"],
                r["verdict"],
                r["rows"],
                r["classified_leaf"],
                r["classified_other"],
                " %s" % r["top_other"] if r["top_other"] else "",
                r["not_built"],
            )
        )
        # Print the terms so a thin label set is visible: add local names
        # ("Soltuna", "luncheon", "dầu bắp") with --terms and re-run.
        print("    terms %s" % ", ".join(r["terms"]))
        if r["rows"]:
            print("    sources %s" % r["sources"])
        for s in r["samples"]:
            print("    - %s" % s)
    n_abs = sum(r["verdict"] == "absent" for r in rows)
    print(
        "\n%d absent (discovery targets), %d in_corpus (classifier/trust gaps)"
        % (n_abs, len(rows) - n_abs)
    )
    if args.out:
        pd.DataFrame(rows).to_csv(args.out, sep="\t", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
