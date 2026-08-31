#!/bin/bash
# Commit the per-source archived-page tier in template-repo.
#
# This session is worktree-isolated to pacific-observatory, and the harness
# refuses any git command aimed at the template-repo checkout -- via `cd`,
# `-C`, or `--git-dir` alike. The edits are applied, linted and tested; only
# the commit needs a shell that is not worktree-isolated.
#
#   bash infra/commit_bysource_tier.sh
#
# If infra/commit_offer_scope.sh has not been run yet, run it first: it commits
# the microdata Offer-scope fix, which is a separate change to a separate file.
#
# Nothing under data/, outputs/ or openspec/ is staged, and no Co-Authored-By
# trailer is added.
set -eu

REPO=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "on $BRANCH -- creating a branch rather than committing to it"
  git checkout -b cc-bysource-tier
fi

git add \
  src/prices/price_scraping/archived_bysource.py \
  src/prices/cc_warc_fetcher.py \
  tests/unit/prices/test_archived_bysource.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(parse): per-source tier for rakuten, ebay_uk and tata_1mg, measured

Three sources hold 3.2M of the 18M misses and published no portable surface in
the era Common Crawl captured them, so every generic tier abstains and the page
banks nothing. Each does write its price into a stable class, so this tier reads
those classes directly. It runs after every generic surface and returns nothing
for any source without an extractor, so it only reaches pages already banked as
a miss: over all 541 cached pages, 0 rows changed and 175 pages gained.

Held-out yield, measured on 165 pages fetched from the miss corpus before the
extractors were written and never looked at while writing them:

  ebay_uk    43 of 55 live pages   78.2%
  tata_1mg   51 of 55 live pages   92.7%
  rakuten     2 of 14 live pages   14.3%

Holding the design and measurement sets apart is what made this correct. Three
defects were invisible on the pages the extractors were shaped against and
obvious on the held-out ones:

- rakuten titles are sometimes the category path, and those are exactly the
  URLs holding several variants of one item, so a title-derived name paired a
  breadcrumb with whichever variant's price came first. Counting `item_name`
  separates a single item from a variant page the tier cannot pair up.
- tata_1mg spans three templates, and taking the MRP in all three would have
  put a discounted price in one year against a sticker price in the next. Each
  era's unconditional price is taken instead: outright in the oldest, the MRP
  in the era whose only discount is basket-gated, the open offer price in the
  era that also prints a members-only one.
- ebay renamed its price box `vi-price-np`, which cost three sterling pages.

rakuten's 14.3% is the corpus, not the extractor: 31 of its 55 held-out pages
are error pages for delisted products and 9 more are multi-variant pages, and
all 12 of its abstentions were checked by hand and are correct. Its 1.37M
misses are worth ~50k rows, against ~1.13M for ebay_uk.

Every extractor abstains rather than guesses, because these pages carry many
figures that are not the product's price -- postage, loyalty points, a
manufacturer's list price, seventeen recommendations in `.mfe-price`, a
substitute drug's rail, a foreign-currency conversion -- and banking one writes
a wrong number into a series where nothing downstream can detect it.
MSG

git --no-pager log --stat -1
