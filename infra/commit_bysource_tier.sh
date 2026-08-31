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
  src/prices/price_scraping/archived.py \
  src/prices/price_scraping/archived_bysource.py \
  src/prices/price_scraping/archived_lohaco.py \
  src/prices/price_scraping/archived_eu.py \
  src/prices/cc_warc_fetcher.py \
  tests/unit/prices/test_archived_bysource.py \
  tests/unit/prices/test_archived_lohaco.py \
  tests/unit/prices/test_archived_eu.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(parse): per-source tier for seven archived sources, measured

Seven sources hold 6.4M of the 18M misses and published no portable surface in
the era Common Crawl captured them, so every generic tier abstains and the page
banks nothing. This tier reads each one on its own terms. It runs after every
generic surface and returns nothing for any source without an extractor, so it
only reaches pages already banked as a miss: over all 711 cached pages, 0 rows
changed and 187 pages gained; over all 1,901 once the last three landed, 0
changed again.

Yield, measured on pages fetched from the miss corpus before the extractors
were written and never looked at while writing them:

  ebay_uk          43 of 55 live pages   0.78 rows per capture
  tata_1mg         51 of 55 live pages   0.93
  rakuten           2 of 55 live pages   0.04
  yahoo_shopping   54 rows on 80 pages   0.68

Against measured miss volume that projects to ~3.4M rows, or +10.4% on the
32.8M already banked, and yahoo_shopping is over half of it.

Holding the design and measurement sets apart is what made this correct. Four
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
- yahoo_shopping banked a 650 yen postage quote and a 540 yen order-guide fee,
  each the only row its capture produced.

yahoo_shopping is not one shop but 21,814 of them, each given a free-form
storefront, so there is no class to key on: over 96 captures the most common
class wrapping a real price appears on six. It is read by structure instead --
a repeated block holding one product link and one yen figure -- which means the
figures that are not prices have to be excluded deliberately. Two guards there
are not vocabulary rules and so survive markup the tier has never seen: a name
carrying several different prices on one page does not identify a product (that
is a shipping rate table), and a capture yielding a single pair is not a grid.
The second cost one real row across 170 captures and removed every wrong one.
Widening the noise vocabulary to the name was measured and rejected instead: it
took six real products with it, because a Japanese title advertising 送料無料 is
naming free shipping, not charging for it.

rakuten's 0.04 is the corpus, not the extractor: 31 of its 55 held-out pages
are error pages for delisted products and 9 more are multi-variant pages, and
all 12 of its abstentions were checked by hand and are correct.

Three more sources were added on the same protocol, and two of them corrected
a scouting estimate rather than confirming it:

  lohaco       19.51 rows per capture over 80 held-out pages   ~4.13M rows
  edeka24_de    0.96 rows per capture over 121 captures        ~135k
  elvi_lv       0.06 rows per capture over 816 captures        ~3.4k

That brings the tier to ~7.7M projected rows, +23.4% on the 32.8M banked.

lohaco prices 8 to 52 other products per capture from a ranking rail, on a
class that is 100% precise. Its wrinkle is identity, not extraction: 284 of 880
product links route through a signed ad redirect whose query string is unique
on every occurrence, so banking the href as given would hand the same product a
new identity on every capture and leave a price series that cannot join to
itself. The redirect's `code` parameter rebuilds the canonical item path, which
also exposes 23 same-page duplicates that were invisible before. Its name comes
from the card title rather than the anchor text, so the rank badge and the
appended price are never seen and no stripping is written at all.

edeka24_de's `price-note` sits beside the price and looks exactly like one, but
all 72 values in the design cache carry a unit suffix: it is the Grundpreis,
the per-kilogram reference price German retailers must print. Banking it would
have rescaled every price by pack size in both directions at once -- a Riesling
33% high, a pack of crackers 45% low -- so no magnitude check downstream would
have found it. The charged figure is the sibling div, scoped to the article
widget because a recommendation rail reuses both classes up to eight times per
page.

elvi_lv yields almost nothing, and that is the finding. It is a weekly promo
flyer rather than a checkout store: a product prints a price only inside its
promotion window, and 83% of captures say the promotion ended. The 2.77 rows
per capture it was scouted at came from counting the classes page-wide, which
mostly counted a related-products rail. What it does bank is composed entirely
of discounted prices, which is a bias any consumer of the series has to know
about.

Every extractor abstains rather than guesses, because these pages carry many
figures that are not the product's price -- postage, loyalty points, a
manufacturer's list price, seventeen recommendations in `.mfe-price`, a
substitute drug's rail, a foreign-currency conversion, a free-postage threshold
-- and banking one writes a wrong number into a series where nothing downstream
can detect it.
MSG

git --no-pager log --stat -1
