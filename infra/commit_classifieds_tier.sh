#!/bin/bash
# Commit the classifieds extractors in template-repo.
#
# This session is worktree-isolated to pacific-observatory, and the harness
# refuses any git command aimed at the template-repo checkout -- via `cd`,
# `-C`, or `--git-dir` alike. The edits are applied and tested; only the commit
# needs a shell that is not worktree-isolated.
#
#   bash infra/commit_classifieds_tier.sh
#
# Run this FOURTH, after commit_offer_scope.sh, commit_bysource_tier.sh and
# commit_nextdata_tier.sh. Each of the last three edits archived_bysource.py,
# so committing out of order carries the others' work under the wrong message.
#
# Nothing under data/, outputs/ or openspec/ is staged, and no Co-Authored-By
# trailer is added.
set -eu

REPO=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "on $BRANCH -- creating a branch rather than committing to it"
  git checkout -b cc-classifieds-tier
fi

git add \
  src/prices/price_scraping/archived_classifieds.py \
  src/prices/price_scraping/archived_bysource.py \
  tests/unit/prices/test_archived_classifieds.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(parse): classifieds asking prices for three of ten sources, measured

Ten classifieds sources hold 1.71M misses. Three of them state a single item's
asking price next to a name, and are read here. The other seven were measured
and refused; those verdicts are recorded in the module docstring because each
one looks like a yield on any score that does not read its samples.

Measured on held-out captures none of the code was written against, drawn from
the eras that hold each source's volume:

  olx_pk        0.87 rows per capture in 2017, 0.60 in 2018   ~130k
  somon_tj      0.95 in 2016, 0.90 in 2017                     ~97k
  pakwheels_pk  0.13 in both 2017 and 2018                     ~36k

Across all 79 rows: every one carries a name, and every banked price appears in
the digits its own page renders.

pakwheels is the reason the rail guard exists, and its held-out rate is a third
of what the class score promised. `generic-green` covers 93% of captures, and
on the 2017 template -- 39% of that source's misses -- every single occurrence
is inside `recent-vehicle-list-content`, a rail of other people's listings. The
page's own price is not server-rendered there at all. Taking the class would
have attributed a different car's asking price to this URL on nearly every
2017 capture, and the series would have moved whenever the rail rotated.

Two more guards come from rows banked wrongly before they existed:

- A figure spanning two values is a band, not a price. olx_pk's 2018 era
  carries job adverts under exactly the markup goods use, and their
  `pricelabel` holds a monthly salary range ("Rs 12,000 - 15,000" against
  "Staff required as data entry operator").
- Several distinct prices outside the rail means the capture is a category
  listing, whose `h1` is the search query ("Used Cars for Sale in Faisalabad")
  rather than any item's name. Pairing that heading with whichever price came
  first invents a product, and it did on 10 of 15 pakwheels captures in 2013.

Pakistani pages group digits in the lakh convention, where "Rs 16,00,000" is
1,600,000 rather than 160,000. `normalize_price` already handles it; it is
called out here because the verification check did not, and reported four
correct rows as unrendered until it was fixed.

These rows are asking prices from mostly private sellers, frequently for
second-hand goods, and somon_tj and pakwheels_pk mix goods with property,
rents and services in the same markup. That is a real property of the source,
not a defect, but nothing downstream can infer it from the row.
MSG

git --no-pager log --stat -1
