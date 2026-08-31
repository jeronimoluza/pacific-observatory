#!/bin/bash
# Commit the unclaimed-Offer scope fix in template-repo.
#
# This session is worktree-isolated to pacific-observatory, and the harness
# refuses any git command aimed at the template-repo checkout -- via `cd`,
# `-C`, or `--git-dir` alike. The edits are applied and tested; only the commit
# needs a shell that is not worktree-isolated.
#
#   bash infra/commit_offer_scope.sh
#
# Nothing under data/, outputs/ or openspec/ is staged, and no Co-Authored-By
# trailer is added.
set -eu

REPO=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "on $BRANCH -- creating a branch rather than committing to it"
  git checkout -b cc-offer-scope
fi

git add \
  src/prices/price_scraping/archived_microdata.py \
  tests/unit/prices/test_archived_microdata.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(microdata): read an Offer no Product claims, measured

The tier gated on a top-level Product itemscope, so a page whose price hangs
on an Offer that no Product encloses was skipped whole. Two shapes in the miss
corpus do exactly that: chemist_warehouse stands a legacy
data-vocabulary.org/Offer alone, liverpool_mx nests a schema.org/Offer inside
a WebPage. The namespace was never the obstacle -- _type_of already strips it
-- the Product-only gate was, which is why testing standalone-ness alone still
missed liverpool_mx and the condition is "no Product ancestor" instead.

The Product pass runs first and returns untouched, so a page that parses today
parses identically. Measured over 376 cached miss pages: 0 rows lost, 0 rows
changed, 35 pages newly read -- chemist_warehouse 30 of 42, liverpool_mx 5 of
8, the other 3 being SPA shells carrying no microdata at all.

A bare Offer carries no name, so it borrows og:title. That is sound for one
offer and a guess for several, so more than one abstains rather than stamping
a single title onto every price on the page.

Reading those pages exposed a latent defect the tier had never hit:
chemist_warehouse hangs itemprop=price on a wrapper whose subtree text reads
"$59.00 FRENZY SALE $59.00 $59.00", and stripping non-digits banked
590059005900. _price_value passes leaf elements straight through -- every case
the tier read before -- and for a wrapper takes the figure only when the
subtree agrees on one, abstaining on a was/now pair it cannot rank. That fixed
6 of the first-pass rows and correctly dropped a seventh.

The banked corpus is unaffected: 14 of 402,183 sampled microdata rows look
concatenated (0.0035%), and the sampled examples are false positives of the
detector rather than real mangling.
MSG

git --no-pager log --stat -1
